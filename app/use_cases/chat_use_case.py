import re
from sqlalchemy.orm import Session

from app.services import cache_service, llm_client
from app.services.ai_response_service import enhance_response
from app.services.llm_text_service import describe_conditions
from app.schemas.conversation_intent import ConversationIntent
from app.services.conversation_intent_service import classify_conversation_intent


from app.services.conversation_service import (
    get_active_search_task,
    get_or_create_session,
    resolve_follow_up_message,
)
from app.services.conversation_resolution_service import (
    resolve_message_from_active_task,
)
from app.services.intent_router import (
    detect_intent,
    extract_price_query,
    extract_price_sku,
    extract_size_from_query,
    strip_greeting,
)
# 22.10 (этап 3, п.4): карточка условий разговора — ИИ понимает одно сообщение, программа ведёт разговор
from app.services.conversation_state_service import (
    SEARCH,
    RESET_DONE,
    UNCLEAR,
    has_anchor,
    Decision,
    CLARIFY,
    SearchState,
    describe_state,
    merge,
    patch_from_ai,
    patch_from_rules,
    search_filters,
    search_text,
    state_from_dict,
    state_to_dict,
)
from app.services.llm_understanding_service import needs_understanding, understand


from app.services import request_timings
from app.db.session import engine

request_timings.count_sql(engine)   # 15.10: журнал обращений к базе за сообщение → meta.sql

from app.services.promo_service import build_deals_response
from app.services.product_service import (
    get_model_cards_by_page,
    get_product_by_sku_service,
    search_products,
)
from app.services.product_link_service import find_product_link
from app.repositories.product_repository import size_variants
from app.services.search_request_builder import build_search_request
from app.services.scarcity_service import scarce_sizes_by_page

from app.services.response_builder import build_response

from app.services.search_decision_service import (
    apply_search_decision,
    resolve_next_step,
)

from app.services.search_event_service import log_search_event
from app.services.background_log_service import log_after_response
from app.services.translations import translate, resolve_language

from app.services.store_info_service import build_store_answer, build_store_info_response, load_store_info


from app.services.task_flow_service import sync_search_task_after_result
from app.services.task_transition_service import has_own_product_words

_NOT_PROVIDED = object()

HISTORY_SIZE = 4            # сколько прошлых сообщений клиента помнит понимание ИИ
HISTORY_TTL = 1800          # 30 минут тишины — разговор начинается заново

SHOWN_LIMIT = 40            # сколько показанных моделей помним для «другие / кроме этих»


def _page(item) -> str:
    """Страница модели (без ?size=…) — так узнаём «уже показанную» карточку."""
    url = item.get("product_url") if isinstance(item, dict) else getattr(item, "product_url", None)
    return (url or "").split("?")[0]


def _with_updates(context, **updates):
    if hasattr(context, "model_copy"):
        return context.model_copy(update=updates)
    for name, value in updates.items():
        setattr(context, name, value)
    return context


CTA_KEYS = ("cta_1", "cta_2", "cta_3")   # призыв к действию — по очереди, чтобы не звучать одинаково
CTA_MIN_DISCOUNT = 0.3                  # повод для призыва в следующих ответах — скидка от 30%


def _discount_share(item) -> float:
    price = item.get("price_from") or item.get("price")
    regular = item.get("regular_price")
    if not price or not regular or regular <= price:
        return 0.0
    return 1 - price / regular





# 13.10: цвет в базе почти не размечен (~7% товаров) → на вопрос «а в чёрном есть?» не ищем, а ведём на страницу товара
COLOR_WORD = re.compile(
    r"(?<![ა-ჰ])(შავ|თეთრ|წითელ|ლურჯ|მწვან|ნაცრისფერ|ვარდისფერ|ყვითელ|ყავისფერ|სტაფილოსფერ|იისფერ|ფერ)"
    r"|\b(black|white|red|blue|green|gr[ae]y|pink|colou?rs?)\b",
    re.IGNORECASE,
)
# слова о самом товаре: «შავი სარბენი 42» — это уже новый поиск, а не вопрос о цвете
PRODUCT_WORD = re.compile(
    r"(?<![ა-ჰ])(ფეხსაცმ|კედ|ბოტას|ბოტ|სანდალ|ჩუსტ|ქურთუკ|მაისურ|შარვალ|ჟაკეტ|ზედა|ჰუდ|ჩანთ|ზურგჩანთ|ქუდ|წინდ|სარბენ|ბურთ)"
    r"|\b(shoes?|sneakers?|boots?|jackets?|hoodie|pants|shirt|t-shirt|bag|backpack|cap|socks)\b",
    re.IGNORECASE,
)


def is_color_question(message: str) -> bool:
    """Вопрос только про цвет: есть цвет, но нет своего товара, размера или бренда."""
    text = (message or "").strip()
    if not COLOR_WORD.search(text) or PRODUCT_WORD.search(text) or re.search(r"\d", text):
        return False
    request = build_search_request(message=text, limit=1, offset=0)
    return not (request.brand or request.category)


# 19.10 (п.115): «ещё / другие модели» без своих слов о товаре → следующие 5 того же поиска (без ИИ)
MORE_WORDS = {"კიდევ", "კიდე", "სხვა", "სხვები", "მეტი", "kidev", "kide", "sxva",
              "more", "other", "others", "another", "else"}
MORE_FILLER_WORDS = {
    "მაჩვენე", "მაჩვენეთ", "მიჩვენე", "მიჩვენეთ", "მომეცი", "გაქვთ", "გაქ", "არის", "რამე", "გთხოვთ",
    "თუ", "და", "ან", "ხომ", "მოდელი", "მოდელები", "მოდელს", "ვარიანტი", "ვარიანტები", "ვარიანტს",
    "ხუთი", "5", "machvene", "modeli", "modelebi",
    "შემომთავაზე", "შემომთავაზეთ", "შემოგვთავაზე", "მირჩიე", "მირჩიეთ", "ვარიანტებს", "მოდელებს",
    "offer", "suggest", "recommend",
    "show", "me", "please", "any", "do", "you", "have", "some", "model", "models", "option", "options",
    "variant", "variants",
}


def is_more_request(message: str) -> bool:
    """«კიდევ სხვა მოდელი მაჩვენე», «show me more» → True; «სხვა ფერის კედები» (свой товар/цвет/бренд) → False."""
    words = re.findall(r"\w+", (message or "").lower())
    if not words or not any(word in MORE_WORDS for word in words):
        return False
    return all(word in MORE_WORDS or word in MORE_FILLER_WORDS for word in words)

# 21.10: «სხვა ბრენდის მოდელები» — исключить уже показанные бренды (живьём: дважды Adidas, а Nike 23 модели есть)
OTHER_BRAND = re.compile(r"სხვა\s+ბრენდ[ა-ჰ]*|\b(?:other|different|another)\s+brands?\b", re.IGNORECASE)
BRAND_WORDS = {"ბრენდი", "ბრენდის", "ბრენდები", "ბრენდების", "ბრენდს", "brand", "brands", "different"}


def wants_other_brand(message: str) -> bool:
    return bool(OTHER_BRAND.search(message or ""))


def is_other_brand_request(message: str) -> bool:
    """«სხვა ბრენდის მოდელები მაჩვენეთ» → True; «სხვა ბრენდის სარბენი» (свой товар) → обычный путь."""
    words = re.findall(r"\w+", (message or "").lower())
    return wants_other_brand(message) and all(
        word in MORE_WORDS or word in MORE_FILLER_WORDS or word in BRAND_WORDS for word in words)


def search_log_intent(exclude_pages) -> str:
    """20.10: «ещё / другие / кроме этих» пишем в аналитику отдельно — их 0 = «всё уже показали», а не провал поиска."""
    return "product_search_more" if exclude_pages else "product_search"

def _field(item, name: str):
    # Поиск возвращает товары то объектами Product, то словарями — читаем одинаково.
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _serialize_item(item) -> dict:
    return {
        "id": _field(item, "id"),
        "sku": _field(item, "sku"),
        "name": _field(item, "name"),
        "price": _field(item, "price"),
    }

class ChatUseCase:

    def process_text(self, db: Session, user_id: str, message: str, locale: str, limit: int = 5, offset: int = 0,
                     action: str | None = None):
        """15.10: тот же ответ + meta.timings — время по этапам (понимание / поиск / текст ИИ / прочее / всего).
        26.10: action — нажатая кнопка виджета («more» / «new_search»): команда, а не текст — угадывать не нужно."""
        timings, token, started = request_timings.start()
        response = None
        try:
            if action in ("more", "new_search"):
                response = self._handle_action(db, user_id, action, message, resolve_language(message, locale),
                                               limit, offset)
            else:
                response = self._process_text(db, user_id, message, locale, limit, offset)
        finally:
            response = request_timings.finish(response, timings, token, started)
        return response

    def _process_text(
            self,
            db: Session,
            user_id: str,
            message: str,
            locale: str,
            limit: int = 5,
            offset: int = 0,
    ):
        # Язык ответа: грузинские буквы в сообщении → ka; иначе язык страницы (locale); иначе ka.
        locale = resolve_language(message, locale)
        # 22.10 (шаг 2а): «გამარჯობათ + вопрос» → отвечаем на вопрос (только приветствие — остаётся как есть)
        message = strip_greeting(message) or message

        # U2.4: прошлые сообщения клиента — ИИ понимает продолжение («не женские, а для мальчика»)
        history = self._recent_messages(user_id)
        self._remember_message(user_id, message, history)

        # 26.10 (этап 3, п.2): ссылка на товар topsport.ge → эта модель (точный адрес в базе), без ИИ.
        # Раньше адрес читался как слова: «…-jempri-25» → бренд + «размер 25» → чужие товары.
        link = find_product_link(message)
        if link:
            return self._handle_product_link(db, user_id, link, locale)

        with request_timings.stage("session"):
            session = get_or_create_session(
                db=db,
                user_id=user_id,
            )

        conversation_intent = classify_conversation_intent(message)

        conversation_response = self._handle_conversation_intent(
            conversation_intent=conversation_intent,
            db=db,
            user_id=user_id,
            message=message,
            locale=locale,
            limit=limit,
            offset=offset,
        )

        if conversation_response:
            return conversation_response

        # Вопросы о магазине (доставка, возврат, оплата, магазины, контакты) — ответ из app/config/store_info.json
        store_info_response = build_store_info_response(message, user_id, locale)
        if store_info_response:
            return store_info_response

        with request_timings.stage("active_task"):
            active_task = get_active_search_task(
                db=db,
                session=session,
            )


        # 13.10: «а в чёрном есть?» — цвет не ищем (в базе его почти нет), ведём на страницу товара
        color_response = self._handle_color_question(
            user_id, message, locale, in_conversation=active_task is not None or bool(history))
        if color_response:
            return color_response

        # 26.10 (шаг 5): «ещё» / «другой бренд» / повтор — по карточке условий (раньше: текст задачи + chat:deal)
        state_query, state_filters = self._current_search(user_id)

        # 19.10 (п.115): «ещё модели» → следующие 5 того же поиска (пол, размер, бюджет те же).
        # Решение поиска, а не ИИ: Gemini не зовём (−3 с), работает и когда ИИ не успел.
        if state_query and is_more_request(message):
            return self._show_more_or_same(
                db, user_id, state_query, locale, limit, offset, "more_request",
                session=session, active_task=active_task, customer_message=message, **state_filters,
            )

        # 21.10: «სხვა ბრენდის მოდელები» → тот же поиск, те же условия, но без уже показанных брендов (без ИИ)
        if state_query and is_other_brand_request(message):
            return self._handle_product_search(
                db, user_id, state_query, locale, limit, offset, "more_request",
                session=session, active_task=active_task, customer_message=message, **state_filters,
                exclude_brands=self._shown_brands(user_id),
            )

        # U2.2 (12.10): правила НЕ поняли сообщение → ИИ понимает (translit, болтовня, «эта модель», подарок).
        # Только понимание: товары выбирает наш поиск. ИИ выключен / недоступен → None → всё как раньше.
        understood_response = self._handle_understanding(
            db, user_id, message, locale, limit, offset,
            session=session, active_task=active_task, history=history,
        )
        if understood_response:
            return understood_response

        resolution = resolve_message_from_active_task(
            task=active_task,
            message=message,
        )

        if not resolution.should_search:
            # 19.10: повтор того же вопроса → не сухое «запрос уже обработан», а следующие варианты (новых нет → те же)
            return self._show_more_or_same(
                db, user_id, state_query or resolution.query, locale, limit, offset, resolution.reason,
                session=session, active_task=active_task, customer_message=message, **state_filters,
            )
        resolved_message = resolve_follow_up_message(
            session=session,
            message=resolution.query,
        )



        intent = detect_intent(resolved_message)

        handlers = {
            "empty": self._handle_empty,
            "greeting": self._handle_greeting,
            "sku_search": self._handle_sku_search,
            "product_search": self._handle_product_search,
            "price_check": self._handle_price_check,
        }

        # 22.10 (шаг 2б): поиск товара (ИИ не успел / выключен) → карточка условий, как и в пути ИИ.
        # Сообщение клиента как есть (без склейки с прошлым запросом): что в нём сказано — заменяет своё,
        # остальное остаётся. Ждём ответа на наш вопрос («რა ზომას ეძებთ?») — «42» тоже сюда.
        if intent == "product_search" or (intent != "empty" and self._waiting_for_answer(user_id)):
            return self._search_by_state(
                db, user_id, patch_from_rules(message), message, locale, limit, offset,
                session=session, active_task=active_task, resolution_reason=resolution.reason,
            )

        handler = handlers.get(intent, self._handle_unknown)

        return handler(
            db,
            user_id,
            resolved_message,
            locale,
            limit,
            offset,
        )

    def _add_scarcity_and_cta(self, db, user_id, locale, response, first_answer: bool) -> None:
        """13.10: значок «🔥 დარჩა 2 ზომა» на карточках с реальным дефицитом размеров (scarcity_service)
        и призыв к действию в следующих ответах — только по поводу: дефицит или скидка ≥ 30%.
        В первом ответе призыв уже есть (AVAILABILITY_CTA в response_builder)."""
        items = ((response.get("data") or {}).get("results") or {}).get("items") or []
        if not items:
            return
        scarce = scarce_sizes_by_page(db, [_page(item) for item in items])
        for item in items:
            sizes_left = scarce.get(_page(item))
            if sizes_left and isinstance(item, dict):
                item["scarce_label"] = translate("card_scarce", locale).format(n=len(sizes_left))
                item["sizes_left"] = sizes_left
        if first_answer:
            return
        if scarce:
            cta = translate("cta_scarce", locale)
        elif any(_discount_share(item) >= CTA_MIN_DISCOUNT for item in items if isinstance(item, dict)):
            turn = int(cache_service.get(f"chat:cta:{user_id}") or 0)
            cache_service.set(f"chat:cta:{user_id}", turn + 1, ttl=HISTORY_TTL)
            cta = translate(CTA_KEYS[turn % len(CTA_KEYS)], locale)
        else:
            return
        response["message"] = f"{response.get('message', '')} {cta}".strip()

    @staticmethod
    def _shown_pages(user_id: str) -> list[str]:
        return list(cache_service.get(f"chat:shown:{user_id}") or [])

    @staticmethod
    def _remember_shown(user_id: str, pages: list[str], append: bool) -> None:
        previous = ChatUseCase._shown_pages(user_id) if append else []
        merged = list(dict.fromkeys(previous + [page for page in pages if page]))[-SHOWN_LIMIT:]
        cache_service.set(f"chat:shown:{user_id}", merged, ttl=HISTORY_TTL)

    @staticmethod
    def _shown_brands(user_id: str) -> list[str]:
        return list(cache_service.get(f"chat:brands:{user_id}") or [])

    @staticmethod
    def _remember_brands(user_id: str, items: list, append: bool) -> None:
        previous = ChatUseCase._shown_brands(user_id) if append else []
        brands = [_field(item, "brand") for item in items if _field(item, "brand")]
        cache_service.set(f"chat:brands:{user_id}", list(dict.fromkeys(previous + brands)), ttl=HISTORY_TTL)

    @staticmethod
    def _recent_messages(user_id: str) -> list[str]:
        return list(cache_service.get(f"chat:history:{user_id}") or [])

    @staticmethod
    def _remember_message(user_id: str, message: str, history: list[str]) -> None:
        text = (message or "").strip()
        if text:
            cache_service.set(f"chat:history:{user_id}", (history + [text])[-HISTORY_SIZE:], ttl=HISTORY_TTL)

    def _handle_understanding(self, db, user_id, message, locale, limit, offset, session, active_task,
                              history=None):
        """U2.2: ответ по пониманию ИИ или None (правила поняли сами / ИИ выключен / ИИ не ответил)."""
        if not llm_client.is_enabled():
            return None
        if detect_intent(message) != "product_search":
            return None                      # приветствие, артикул, цена по артикулу — правила знают
        if self._waiting_for_answer(user_id) and self._is_short_answer(message):
            return None                      # 22.10: ответ на наш вопрос («42», «კი», «არა») — правила, без ИИ
        request = build_search_request(message=message, limit=limit, offset=offset)
        is_refinement = active_task is not None and not has_own_product_words(message.strip().lower())
        in_conversation = active_task is not None or bool(history)
        if not needs_understanding(message, brand=request.brand, category=request.category,
                                   is_refinement=is_refinement, in_conversation=in_conversation):
            return None

        with request_timings.stage("understanding"):
            understanding = understand(message, getattr(active_task, "query", None), history)
        result = understanding["result"]
        if result is None:
            request_timings.note_skipped(understanding["errors"])  # 15.10: видно в meta, почему ИИ не помог
            return None  # лимит / таймаут / битый ответ → обычный путь
        # Язык ответа — как у всего чата (грузинские буквы → ka, иначе язык страницы).
        # 12.10: «asdf» на KA-странице ИИ счёл английским → ответ пришёл по-английски.
        language = locale
        meta = {
            "understanding": result["intent"],
            "understanding_model": understanding["model"],
            "understanding_ms": understanding["ms"],
            "understanding_errors": understanding["errors"],  # 15.10: почему первая модель не ответила (замер)
        }
        intent = result["intent"]

        if intent == "small_talk":
            reply = result["reply"]
            return {
                "type": "small_talk",
                "message": reply or translate("small_talk", language),
                "data": {"user_id": user_id},
                "meta": {**meta, "ai_used": bool(reply)},
            }

        if intent == "store_question":
            info = load_store_info()
            text = build_store_answer(result["store_topic"], language, info) if info else None
            if text:
                return {
                    "type": "store_info",
                    "message": text,
                    "data": {"user_id": user_id, "topic": result["store_topic"], "links": info.get("links", {})},
                    "meta": meta,
                }

        if intent == "product_search" and result["discount_only"] and not result["query"] and not result["gift"]:
            # А2: «покажи скидки» без типа товара → подборка скидок вместо «уточните»
            return {**self._handle_deals(db, user_id, locale, limit, result["max_price"]), "meta": meta}

        if intent == "product_search" and result["query"]:
            # 22.10 (шаг 2б): поля ИИ → patch → та же карточка условий, что и без ИИ (одно правило слияния).
            # Пол, размер, бюджет, скидка, новинки — в карточке; текст поиска собирает search_text.
            response = self._search_by_state(
                db, user_id, patch_from_ai(result, message), message, locale, limit, offset,
                session=session, active_task=active_task, resolution_reason="llm_understanding",
                # U2.5: «другие / кроме этих» → не показывать уже показанные модели
                exclude_pages=self._shown_pages(user_id) if result["wants_other"] else None,
                # 21.10: «სხვა ბრენდის…» вместе со своим товаром — без уже показанных брендов
                exclude_brands=self._shown_brands(user_id) if wants_other_brand(message) else None,
            )
            response["meta"] = {**(response.get("meta") or {}), **meta}
            return response

        if intent == "product_search" and result["gift"]:
            key = "gift_suggestion"
        elif intent == "product_question" and result["store_topic"] == "stores":
            key = "product_stock_in_stores"
        elif intent == "product_question":
            key = "clarify_product"
        else:
            key = "unclear_request"
        return {
            "type": "clarify",
            "message": translate(key, language),
            "data": {"user_id": user_id},
            "meta": meta,
        }
    # --- 22.10 (шаг 2б): карточка условий разговора (claude/dialog-state-design.md) ---

    @staticmethod
    def _load_state(user_id: str) -> SearchState | None:
        return state_from_dict(cache_service.get(f"chat:state:{user_id}"))

    @staticmethod
    def _save_state(user_id: str, state: SearchState) -> None:
        cache_service.set(f"chat:state:{user_id}", state_to_dict(state), ttl=HISTORY_TTL)

    def _current_search(self, user_id: str) -> tuple[str | None, dict]:
        """Текущий поиск разговора из карточки: (текст поиска, бюджет / скидка / новинки). Нет карточки → (None, {})."""
        state = self._load_state(user_id)
        query = search_text(state) if state else ""
        if not query:
            return None, {}
        filters = {name: value for name, value in search_filters(state).items() if name != "exclude_brands"}
        return query, filters

    def _waiting_for_answer(self, user_id: str) -> bool:
        """Мы спросили размер / бюджет и ждём ответа — короткий ответ («42», «კი») идёт в карточку."""
        state = self._load_state(user_id)
        return bool(state and state.pending)

    @staticmethod
    def _is_short_answer(message: str) -> bool:
        """Похоже на ответ на наш вопрос: размер, бюджет, «კი / არა / იგივე». «rogor xar?» — нет → это для ИИ."""
        patch = patch_from_rules(message)
        return bool(patch.size or patch.max_price or patch.yes or patch.no)

    def _search_by_state(self, db, user_id, patch, message, locale, limit, offset, session, active_task,
                         resolution_reason, exclude_pages=None, exclude_brands=None):
        """Карточка + сообщение → поиск ИЛИ вопрос (размер / бюджет / что ищем) ИЛИ «новый поиск»."""
        old_state = self._load_state(user_id)
        state, decision = merge(old_state, patch)
        self._save_state(user_id, state)
        if decision.action != SEARCH:
            return self._with_kids_note(self._state_question(user_id, locale, state, decision), patch, locale)

        query = search_text(state)
        search_kwargs = dict(session=session, active_task=active_task, customer_message=message,
                             # 26.10: ЭТО сообщение принесло незнакомые слова (правила, ИИ не успел), а товара /
                             # бренда / модели нет → показываем, только если нашлось ПО СЛОВАМ
                             keyword_required=bool(patch.loose_text) and not has_anchor(state),
                             **search_filters(state))
        if exclude_brands:
            search_kwargs["exclude_brands"] = list(exclude_brands)
        nothing_changed = old_state is not None and state_to_dict(old_state) == state_to_dict(state)
        if nothing_changed and not exclude_pages:
            # 15.10: тот же вопрос ещё раз → следующие 5 (новых нет → те же)
            response = self._show_more_or_same(db, user_id, query, locale, limit, offset, resolution_reason,
                                               **search_kwargs)
        else:
            response = self._handle_product_search(db, user_id, query, locale, limit, offset, resolution_reason,
                                                   exclude_pages=exclude_pages, **search_kwargs)
        if response is None:
            # бессмыслица не остаётся в карточке «товаром»: пол / размер / бюджет — остаются
            state.product_text = None
            self._save_state(user_id, state)
            return self._state_question(user_id, locale, state, Decision(UNCLEAR))
        response["meta"] = {**(response.get("meta") or {}), "understood_query": query,
                            "max_price": state.max_price, "discount_only": state.discount_only,
                            "new_only": state.new_only, "dialog_state": describe_state(state)}
        return self._with_kids_note(response, patch, locale)

    @staticmethod
    def _with_kids_note(response, patch, locale):
        """26.10 (замер): детское в каталоге не делится на девочек / мальчиков — честно говорим об этом."""
        if patch.child:
            response["message"] = f"{translate('kids_unisex_note', locale)} {response.get('message') or ''}".strip()
        return response

    def _handle_product_link(self, db, user_id, link, locale):
        """Карточка модели по ссылке + где проверить наличие в филиале. Размер: из текста клиента
        («ეს 38 ზომაში?» → есть / нет) или из ссылки (?size=36 → только «есть», если есть)."""
        with request_timings.stage("search"):
            cards = get_model_cards_by_page(db, link.page)
        if not cards:
            return {
                "type": "product_link",
                "message": translate("product_link_not_found", locale),
                "data": {"user_id": user_id, "results": {"items": []}},
                "meta": {"ai_used": False, "ai_mode": "template"},
            }
        card = cards[0]
        asked_size = extract_size_from_query(link.rest) if link.rest else None
        size = asked_size or link.size
        has_size = bool(size) and any(str(item).upper() in size_variants(size) for item in card.get("sizes") or [])
        if has_size:
            note = translate("product_link_size_yes", locale).format(size=size)
        elif asked_size:
            note = translate("product_link_size_no", locale).format(size=asked_size)
        else:
            note = ""
        # карточка условий = эта модель: дальше «а 38?» продолжает разговор о ней
        state, _ = merge(None, patch_from_rules(f"{card.get('name') or ''} {size or ''}"))
        self._save_state(user_id, state)
        self._remember_shown(user_id, [_page(card)], append=False)
        return {
            "type": "product_link",
            "message": f"{note} {translate('product_link_found', locale)}".strip(),
            "data": {"user_id": user_id,
                     "results": {"query": size or "", "items": [card], "total": 1, "has_more": False}},
            "meta": {"dialog_state": describe_state(state), "ai_used": False, "ai_mode": "template"},
        }

    def _handle_action(self, db, user_id, action, message, locale, limit, offset):
        """26.10 (шаг 4): кнопки под карточками.
        «ახალი ძებნა» → карточка пустая, показанное забыто → подсказка с примером.
        «კიდევ ვარიანტები» → следующие 5 по той же карточке (те же пол, размер, бюджет, новинки)."""
        if action == "new_search":
            self._save_state(user_id, SearchState())
            self._remember_shown(user_id, [], append=False)
            cache_service.set(f"chat:history:{user_id}", [], ttl=HISTORY_TTL)   # ИИ тоже начинает с чистого листа
            return self._state_question(user_id, locale, SearchState(), Decision(RESET_DONE))
        state = self._load_state(user_id)
        query = search_text(state) if state else ""
        if not query:
            return self._state_question(user_id, locale, SearchState(), Decision(CLARIFY, ["product"]))
        response = self._show_more_or_same(db, user_id, query, locale, limit, offset, "more_request",
                                           customer_message=message, **search_filters(state))
        response["meta"] = {**(response.get("meta") or {}), "understood_query": query,
                            "dialog_state": describe_state(state)}
        return response

    def _state_question(self, user_id, locale, state, decision):
        """Вопрос без карточек товаров: только о том, чего не хватает (решение пользователя 21.10)."""
        if decision.action == UNCLEAR:
            key = "unknown"                    # 26.10: «не поняла + пример» (translations.unknown, 16.10)
        elif decision.action == RESET_DONE:
            key = "state_new_search"
        elif decision.action == CLARIFY:
            key = "state_need_product"
        elif decision.ask == ["budget"]:
            key = "state_ask_budget"
        elif "budget" in decision.ask:
            key = "state_ask_size_budget"
        else:
            key = "state_ask_size"
        text = translate(key, locale)
        if "{budget}" in text:
            text = text.format(budget=f"{state.max_price:g}" if state.max_price else "")
        return {
            "type": "clarify",
            "message": text,
            "data": {"user_id": user_id},
            "meta": {"dialog_state": describe_state(state), "ask": list(decision.ask),
                     "ai_used": False, "ai_mode": "template"},
        }

    def _show_more_or_same(self, db, user_id, query, locale, limit, offset, resolution_reason, **search_kwargs):
        """15.10 (решение пользователя): повтор вопроса → следующие варианты; новых нет → те же карточки."""
        shown = self._shown_pages(user_id)
        if not shown:
            # не помним, что показывали (прошло больше 30 минут) — обычный поиск
            return self._handle_product_search(db, user_id, query, locale, limit, offset, resolution_reason,
                                               **search_kwargs)
        response = self._handle_product_search(db, user_id, query, locale, limit, offset, resolution_reason,
                                               exclude_pages=shown, **search_kwargs)
        if response is None:
            return None                       # 26.10: «не поняла» (только смысловой на незнакомые слова)
        if ((response.get("data") or {}).get("results") or {}).get("items"):
            response["message"] = translate("repeat_more", locale)
            response["meta"] = {**(response.get("meta") or {}), "ai_used": False, "ai_mode": "template"}
            return response
        response = self._handle_product_search(db, user_id, query, locale, limit, offset, resolution_reason,
                                               **search_kwargs)
        response["message"] = translate("repeat_same", locale)
        response["meta"] = {**(response.get("meta") or {}), "ai_used": False, "ai_mode": "template"}
        return response





    def _handle_deals(self, db, user_id, locale, limit, max_price=None):
        """А2 (12.10): подборка скидок — логика в promo_service.build_deals_response (её же зовёт кнопка виджета)."""
        return build_deals_response(db, user_id, locale, limit=limit, offset=0, max_price=max_price)

    def _handle_color_question(self, user_id, message, locale, in_conversation):
        """13.10 (решение пользователя): вопрос только про цвет в разговоре → страница товара, без поиска."""
        if not in_conversation or not is_color_question(message):
            return None
        return {
            "type": "color_question",
            "message": translate("color_on_product_page", locale),
            "data": {"user_id": user_id},
        }

    def _handle_conversation_intent(
            self,
            conversation_intent: ConversationIntent,
            db: Session,
            user_id: str,
            message: str,
            locale: str,
            limit: int,
            offset: int,
    ):
        conversation_handlers = {
            ConversationIntent.GREETING: lambda: self._handle_greeting(
                db, user_id, message, locale, limit, offset
            ),
            ConversationIntent.GRATITUDE: lambda: self._handle_gratitude(user_id, locale),
            ConversationIntent.FAREWELL: lambda: self._handle_farewell(user_id, locale),
            ConversationIntent.SMALL_TALK: lambda: self._handle_small_talk(user_id, locale),
        }

        handler = conversation_handlers.get(conversation_intent)

        if handler:
            return handler()

        return None


    def _handle_gratitude(self, user_id: str, locale: str = "ka"):
        return {
            "type": "gratitude",
            "message": translate("gratitude", locale),
            "data": {
                "user_id": user_id,
            },
        }

    def _handle_farewell(self, user_id: str, locale: str = "ka"):
        return {
            "type": "farewell",
            "message": translate("farewell", locale),
            "data": {
                "user_id": user_id,
            },
        }

    def _handle_small_talk(self, user_id: str, locale: str = "ka"):
        return {
            "type": "small_talk",
            "message": translate("small_talk", locale),
            "data": {
                "user_id": user_id,
            },
        }

    def _handle_empty(self, db, user_id, message, locale, limit, offset):
        return {
            "type": "empty",
            "message": translate("empty", locale)
        }

    def _handle_unknown(self, db, user_id, message, locale, limit, offset):
        return {
            "type": "unknown",
            "message": translate("unknown", locale)
        }

    def _handle_greeting(self, db, user_id, message, locale, limit, offset):
        return {
            "type": "greeting",
            "message": translate("greeting", locale)
        }

    def _handle_sku_search(self, db, user_id, message, locale, limit, offset):

        product_result = get_product_by_sku_service(db, message)
        item = product_result.items[0] if product_result.items else None

        log_search_event(
            db=db,
            user_id=user_id,
            query=message,
            locale=locale,
            intent="sku_search",
            items=[item] if item else [],
        )

        return self._build_sku_response(user_id, product_result, locale)

    def _handle_product_search(
            self,
            db,
            user_id,
            message,
            locale,
            limit,
            offset,
            resolution_reason=None,
            session=_NOT_PROVIDED,
            active_task=_NOT_PROVIDED,
            max_price=None,
            discount_only=False,
            exclude_pages=None,
            prefer_discount=False,
            customer_message=None,
            new_only=False,
            exclude_brands=None,
            keyword_required=False,
    ):

        exclude = set(exclude_pages or [])
        search_request = build_search_request(
            message=message,
            limit=limit,
            offset=offset,
        )
        if max_price or discount_only:      # U2.3: фильтры от понимания ИИ
            search_request = search_request.model_copy(
                update={"max_price": max_price, "discount_only": discount_only})
        if prefer_discount and not discount_only:   # 13.10: «сначала со скидкой» — порядок, а не фильтр
            search_request = search_request.model_copy(update={"prefer_discount": True})
        if new_only:                         # 21.10: «ახალი კოლექცია» — только новинки магазина
            search_request = search_request.model_copy(update={"new_only": True})
        if exclude_brands:                   # 21.10: «სხვა ბრენდის» — без уже показанных брендов
            search_request = search_request.model_copy(update={"exclude_brands": list(exclude_brands)})
        if exclude:                          # U2.5: берём с запасом — показанные потом уберём
            search_request = search_request.model_copy(update={"limit": limit + len(exclude)})

        with request_timings.stage("search"):
            products = search_products(db, search_request)
            products = apply_search_decision(products, search_request)
        if keyword_required and getattr(products, "matched_by", None) == "semantic":
            # 26.10 (замер measure_semantic_floor): на незнакомые слова по словам 0, а смысловой всегда
            # приносит «самое похожее» — бессмыслица «ქწერტ» 0.670 выше настоящего «swimming» 0.641,
            # порог их не разделяет. Решение: это «не поняла», а не товары (текст ИИ и аналитику не тратим).
            return None

        if exclude:
            kept = [item for item in products.items if _page(item) not in exclude]
            removed = len(products.items) - len(kept)
            products = _with_updates(products, items=kept[:limit],
                                     total_count=max(0, (products.total_count or 0) - removed), limit=limit)
        next_step = resolve_next_step(products.result_mode)


        if session is _NOT_PROVIDED:
            session = get_or_create_session(db=db, user_id=user_id)

        if active_task is _NOT_PROVIDED:
            active_task = get_active_search_task(db=db, session=session)

        with request_timings.stage("task_sync"):
            sync_search_task_after_result(
                db=db,
                session=session,
                active_task=active_task,
                query=products.query,
                result_mode=products.result_mode,
                detected_brand=search_request.brand,
                detected_size=search_request.size,
                current_step=next_step,
                resolution_reason=resolution_reason,
            )



        # 13.10: «наличие в филиале — на странице товара» говорим один раз за разговор, дальше коротко
        hint_key = f"chat:stock_hint:{user_id}"
        stock_hint = not cache_service.get(hint_key)
        extra = {} if stock_hint else {"stock_hint": False}
        base_response = build_response(products, user_id, "product_search", locale, **extra)
        if stock_hint and products.items:
            cache_service.set(hint_key, True, ttl=HISTORY_TTL)
        with request_timings.stage("scarcity_cta"):
            self._add_scarcity_and_cta(db, user_id, locale, base_response, first_answer=stock_hint)
        if (exclude or exclude_brands) and not products.items:
            # честно: под эти условия других моделей / брендов нет — всё уже показали
            base_response["message"] = translate("search_no_other", locale)
        # 13.10: ИИ видит то, что НАПИСАЛ клиент, и понятые условия → отвечает на сам вопрос
        conditions = describe_conditions(search_request.size, max_price, discount_only, prefer_discount, new_only)
        with request_timings.stage("ai_text"):
            response = enhance_response(base_response, products, customer_message=customer_message or message,
                                        conditions=conditions)
        shown_items = (response.get("data") or {}).get("results", {}).get("items") or []
        self._remember_shown(user_id, [_page(item) for item in shown_items], append=bool(exclude))
        self._remember_brands(user_id, shown_items, append=bool(exclude or exclude_brands))
        with request_timings.stage("log_event"):
            # 16.10: аналитика — после ответа, в фоне (клиент её не ждёт)
            log_after_response(
                log_search_event,
                db,
                user_id=user_id,
                query=message,
                locale=locale,
                intent=search_log_intent(exclude or exclude_brands),
                items=products.items,
                search_context=products,
                ai_meta=response.get("meta"),
            )

        return response

    def _handle_price_check(self, db, user_id, message, locale, limit, offset):

        sku = extract_price_sku(message)

        if sku:
            product_result = get_product_by_sku_service(db, sku)
            item = product_result.items[0] if product_result.items else None

            log_search_event(
                db=db,
                user_id=user_id,
                query=message,
                locale=locale,
                intent="price_check",
                items=[item] if item else [],
            )

            return self._build_price_response(user_id, product_result, locale)

        query = extract_price_query(message)

        if query:
            search_request = build_search_request(
                message=query,
                limit=limit,
                offset=offset,
            )

            products = search_products(db, search_request)
            items = products.items

            log_search_event(
                db=db,
                user_id=user_id,
                query=message,
                locale=locale,
                intent="price_check",
                items=items,
                search_context=products,
            )

            if len(items) == 1:
                product_result = products
                return self._build_price_response(user_id, product_result, locale)

            if len(items) > 1:
                return self._build_search_response(
                    "price_check",
                    user_id,
                    products,
                    locale,
                )

        return {
            "type": "price_check",
            "message": translate("price_missing_identifier", locale)
        }

    def _build_search_response(
            self,
            response_type: str,
            user_id: str,
            products: dict,
            locale: str | None = None,
    ):
        items = products.items
        limited_items = items[:5]

        serialized_items = [_serialize_item(item) for item in limited_items]

        response = {
            "type": response_type,
            "data": {
                "user_id": user_id,
                "results": {
                    "query": products.query,
                    "items": serialized_items
                }
            }
        }

        if locale:
            size = products.detected_size or extract_size_from_query(products.query or "")

            if size:
                response["message"] = translate("found_in_size", locale).format(
                    count=len(serialized_items), size=size,
                )
            elif len(items) > 5:
                response["message"] = translate("too_many_results_refine", locale)
        return response

    def _build_sku_response(self, user_id: str, product_result: dict, locale: str):
        item = product_result.items[0] if product_result.items else None
        size = product_result.detected_size

        if item is None:
            return {
                "type": "sku_search",
                "data": {
                    "user_id": user_id,
                    "results": {
                        "sku": product_result.base_sku,
                        "item": None,
                        "size": size,
                    }
                },
                "message": translate("sku_not_found", locale)
            }

        serialized_item = _serialize_item(item)

        if size:
            message = translate("sku_size_confirm", locale).format(
                sku=product_result.base_sku,
                size=size,
            )
        else:
            message = translate("sku_ask_size", locale).format(
                sku=product_result.base_sku,
            )

        return {
            "type": "sku_search",
            "data": {
                "user_id": user_id,
                "results": {
                    "sku": product_result.base_sku,
                    "item": serialized_item,
                    "size": size,
                }
            },
            "message": message
        }

    def _build_price_response(self, user_id: str, product_result: dict, locale: str):
        item = product_result.items[0] if product_result.items else None

        if item is None:
            return {
                "type": "price_check",
                "data": {
                    "user_id": user_id,
                    "results": {
                        "sku": product_result.base_sku,
                         "price": None
                    }
                },
                "message": translate("sku_not_found", locale)
            }

        return {
            "type": "price_check",
            "data": {
                "user_id": user_id,
                "results": {
                    "sku": _field(item, "sku"),
                    "name": _field(item, "name"),
                    "price": _field(item, "price"),
                }
            }
        }