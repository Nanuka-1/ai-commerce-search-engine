from sqlalchemy.orm import Session

from app.services.ai_response_service import enhance_response

from app.services.conversation_service import (
    create_search_task,
    get_active_search_task,
    get_or_create_session,
    resolve_follow_up_message,
    update_search_task_query,
)
from app.services.conversation_resolution_service import (
    resolve_message_from_active_task,
)
from app.services.intent_router import (
    detect_intent,
    extract_price_query,
    extract_price_sku,
    extract_size_from_query,
)

from app.services.product_service import (
    get_product_by_sku_service,
    search_products,
)
from app.services.search_request_builder import build_search_request

from app.services.response_builder import build_response

from app.services.search_decision_service import (
    apply_search_decision,
    resolve_next_step,
)

from app.services.search_event_service import log_search_event

from app.services.translations import translate

from app.services.task_state_service import should_create_followup_task

from app.services.task_flow_service import (
    create_followup_task_for_result_mode,
)



class ChatUseCase:
    def process_text(
            self,
            db: Session,
            user_id: str,
            message: str,
            locale: str,
            limit: int = 5,
            offset: int = 0,
    ):
        session = get_or_create_session(
            db=db,
            user_id=user_id,
        )

        active_task = get_active_search_task(
            db=db,
            session=session,
        )

        resolution = resolve_message_from_active_task(
            task=active_task,
            message=message,
        )

        if not resolution.should_search:
            return {
                "type": "duplicate",
                "data": {
                    "user_id": user_id,
                    "results": {
                        "query": resolution.query,
                    },
                },
                "message": "This request was already processed.",
            }

        resolved_message = resolve_follow_up_message(
            session=session,
            message=resolution.query,
        )

        intent = detect_intent(resolved_message)

        intent = detect_intent(resolved_message)

        handlers = {
            "empty": self._handle_empty,
            "greeting": self._handle_greeting,
            "sku_search": self._handle_sku_search,
            "product_search": self._handle_product_search,
            "price_check": self._handle_price_check,
        }

        handler = handlers.get(intent, self._handle_unknown)
        return handler(db, user_id, resolved_message, locale, limit, offset)

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

    def _handle_product_search(self, db, user_id, message, locale, limit, offset):

        search_request = build_search_request(
            message=message,
            limit=limit,
            offset=offset,
        )

        products = search_products(db, search_request)
        products = apply_search_decision(products, search_request)
        next_step = resolve_next_step(products.result_mode)

        session = get_or_create_session(db=db, user_id=user_id)
        active_task = get_active_search_task(db=db, session=session)

        if should_create_followup_task(products.result_mode):

            create_followup_task_for_result_mode(
                db=db,
                session=session,
                query=message,
                result_mode=products.result_mode,
            )

        # else:
        #     if active_task:
        #         complete_search_task(
        #             db=db,
        #             task=active_task,
        #             reason="user_provided_refinement",
        #         )

        else:

            if active_task:

                update_search_task_query(

                    db=db,

                    task=active_task,

                    query=products.query,

                )

            else:

                create_search_task(

                    db=db,

                    session=session,

                    query=products.query,

                    detected_brand=search_request.brand,

                    detected_size=search_request.size,

                    current_step=next_step,

                )



        base_response = build_response(products, user_id, "product_search")
        response = enhance_response(base_response, products)
        log_search_event(
            db=db,
            user_id=user_id,
            query=message,
            locale=locale,
            intent="product_search",
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

        serialized_items = [
            {
                "id": item.id,
                "sku": item.sku,
                "name": item.name,
                "price": item.price,
            }
            for item in limited_items
        ]

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
                response["message"] = f"Found {len(serialized_items)} items in size {size}"
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

        serialized_item = {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "price": item.price,
        }

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
                    "sku": item.sku,
                    "name": item.name,
                    "price": item.price
                }
            }
        }