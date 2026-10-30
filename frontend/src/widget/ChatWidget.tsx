import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { getDeals, sendMessage, sendPhoto } from './api'
import { UI } from './i18n'
import ProductCard from './ProductCard'
import Ticker from './Ticker'
import type { Action, ChatResponse, Lang, Message } from './types'
import './widget.css'

const SIZE_IN_QUERY = /\b(\d{2}(?:\.\d)?|XXS|XS|S|M|L|XL|XXL|XXXL)\b/i

// 26.10 (шаг 4): кнопки под карточками поиска — их нажатие уходит на сервер командой (action), не текстом
const ACTION_LABELS: Record<Lang, Record<Action, string>> = {
  ka: { more: 'კიდევ ვარიანტები', new_search: '🔄 ახალი ძებნა' },
  en: { more: 'More options', new_search: '🔄 New search' },
}

// 30.10: фото — те же ограничения, что на сервере (photo_search_service): jpg / png / webp, до 5 МБ
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_PHOTO_BYTES = 5 * 1024 * 1024
const PHOTO_TEXT: Record<Lang, { button: string; tooBig: string; badType: string }> = {
  ka: { button: 'ფოტოს გაგზავნა', tooBig: 'ფოტო ძალიან დიდია (მაქს. 5 MB) — სცადეთ უფრო პატარა.',
        badType: 'გამოგზავნეთ JPG, PNG ან WEBP ფოტო.' },
  en: { button: 'Send a photo', tooBig: 'The photo is too large (max 5 MB) — please try a smaller one.',
        badType: 'Please send a JPG, PNG or WEBP photo.' },
}

// Текст ответа с кликабельными ссылками («не нашли» содержит ссылку на поиск сайта)
function Linkified({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/[^\s]+)/g)
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part)
          ? <a key={i} href={part} target="_blank" rel="noopener">{part.length > 50 ? part.slice(0, 47) + '…' : part}</a>
          : <span key={i}>{part}</span>,
      )}
    </>
  )
}

// Виджет: кнопка 💬 справа внизу → панель чата (на компьютере ~380px, на телефоне — весь экран).
// Только показывает ответ сервера: ЧТО найти и ЧТО сказать решают поиск, правила и LLM на сервере.
export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [lang, setLang] = useState<Lang>('ka')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const nextId = useRef(1)
  const scrollRef = useRef<HTMLDivElement>(null)
  const photoInput = useRef<HTMLInputElement>(null)
  const t = UI[lang]

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, open])

  const add = (message: Omit<Message, 'id'>) => {
    const id = nextId.current++
    setMessages((list) => [...list, { ...message, id }])
    return id
  }
  const remove = (id: number) => setMessages((list) => list.filter((m) => m.id !== id))

  // Ответ сервера → сообщение бота (общий для чата и подборки скидок)
  function addBotResponse(response: ChatResponse) {
    const results = response.data?.results ?? {}
    const asked = (results.query ?? '').match(SIZE_IN_QUERY)
    const items = results.items ?? []
    // 26.10: под карточками поиска — «კიდევ ვარიანტები» (если есть ещё) и «ახალი ძებნა» (всегда)
    // 30.10: фото с найденными моделями — те же кнопки (кроме «ещё»: похожих показываем сразу до 5)
    const isSearch = (response.type === 'product_search' || response.type === 'photo_search') && items.length > 0
    const actions: Action[] = isSearch
      ? [...(response.type === 'product_search' && results.has_more ? ['more' as Action] : []), 'new_search']
      : []
    add({
      role: 'bot',
      text: response.message ?? '',
      items,
      // «ყველა ვარიანტი საიტზე» — только у подборки скидок (страница распродаж работает);
      // поиск сайта ищет фразу целиком и для обычного поиска часто давал пустую страницу (13.10)
      siteUrl: response.type === 'deals' ? results.site_search_url : undefined,
      aiUsed: Boolean(response.meta?.ai_used),
      askedSize: asked ? asked[1].toUpperCase() : null,
      // «კიდევ 5» — только у подборки скидок (13.10: у обычного поиска тоже есть has_more → кнопка путала клиента)
      moreOffset: response.type === 'deals' && results.has_more ? (results.offset ?? 0) + (results.limit ?? 5) : undefined,
      dealsMaxPrice: results.max_price ?? null,
      conditions: isSearch ? response.meta?.dialog_state : undefined,
      actions,
    })
  }

  async function run(userText: string | null, request: () => Promise<ChatResponse>, photoUrl?: string) {
    if (busy) return
    if (userText || photoUrl) add({ role: 'user', text: userText ?? '', photoUrl })
    setBusy(true)
    const typingId = add({ role: 'bot', text: t.typing, kind: 'typing' })
    try {
      const response = await request()
      remove(typingId)
      addBotResponse(response)
    } catch (error) {
      console.error(error)
      remove(typingId)
      add({ role: 'bot', text: t.error, kind: 'error' })
    } finally {
      setBusy(false)
    }
  }

  function ask(text: string) {
    text = text.trim()
    if (!text) return
    setInput('')
    void run(text, () => sendMessage(text, lang))
  }

  // 30.10: клиент выбрал фото → проверка здесь (чтобы не грузить зря) → сервер ищет похожие модели
  function onPhotoChosen(event: ChangeEvent<HTMLInputElement>) {
    const photo = event.target.files?.[0]
    event.target.value = ''                       // то же фото можно выбрать ещё раз
    if (!photo || busy) return
    if (!PHOTO_TYPES.includes(photo.type)) {
      add({ role: 'bot', text: PHOTO_TEXT[lang].badType, kind: 'error' })
      return
    }
    if (photo.size > MAX_PHOTO_BYTES) {
      add({ role: 'bot', text: PHOTO_TEXT[lang].tooBig, kind: 'error' })
      return
    }
    void run(null, () => sendPhoto(photo, lang), URL.createObjectURL(photo))
  }

  // 26.10: нажата кнопка под карточками → кнопки у этой пачки убираем, на сервер — команда
  function pressAction(action: Action, fromMessageId: number) {
    setMessages((list) => list.map((m) => (m.id === fromMessageId ? { ...m, actions: [] } : m)))
    const label = ACTION_LABELS[lang][action]
    void run(label, () => sendMessage(label, lang, action))
  }

  function showDeals(offset: number, fromMessageId?: number, maxPrice?: number | null) {
    if (fromMessageId !== undefined) {
      // кнопка «კიდევ 5» у прошлой пачки больше не нужна
      setMessages((list) => list.map((m) => (m.id === fromMessageId ? { ...m, moreOffset: undefined } : m)))
    }
    void run(offset === 0 ? t.deals : null, () => getDeals(lang, offset, maxPrice))
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    ask(input)
  }

  if (!open) {
    return (
      <button className="tsw-launcher" onClick={() => setOpen(true)} aria-label={t.open}>💬</button>
    )
  }

  return (
    <div className="tsw-panel" role="dialog" aria-label="TopSport chat">
      <header className="tsw-header">
        <div className="tsw-logo">TOP<span>SPORT</span></div>
        <div className="tsw-title">{t.title}</div>
        <div className="tsw-lang">
          {(['ka', 'en'] as Lang[]).map((code) => (
            <button key={code} className={code === lang ? 'active' : ''} onClick={() => setLang(code)}>
              {code.toUpperCase()}
            </button>
          ))}
        </div>
        <button className="tsw-close" onClick={() => setOpen(false)} aria-label={t.close}>×</button>
      </header>

      <Ticker lang={lang} />

      <div className="tsw-scroll" ref={scrollRef}>
        <div className="tsw-msg bot"><div className="tsw-bubble">{t.hello}</div></div>
        {messages.map((m) => (
          <div key={m.id} className={`tsw-msg ${m.role}`}>
            {m.photoUrl && <img className="tsw-user-photo" src={m.photoUrl} alt="" />}
            {m.text && <div className={`tsw-bubble ${m.kind ?? ''}`}><Linkified text={m.text} /></div>}
            {m.aiUsed && <span className="tsw-ai">{t.ai}</span>}
            {m.conditions && <div className="tsw-conditions">{m.conditions}</div>}
            {m.items && m.items.length > 0 && (
              <div className="tsw-cards">
                {m.items.map((item, i) => (
                  <ProductCard key={(item.product_url ?? '') + i} item={item} askedSize={m.askedSize}
                               viewText={t.view} stockTip={t.stockTip} />
                ))}
              </div>
            )}
            {m.actions && m.actions.length > 0 && (
              <div className="tsw-actions">
                {m.actions.map((action) => (
                  <button key={action} className="tsw-action" onClick={() => pressAction(action, m.id)} disabled={busy}>
                    {ACTION_LABELS[lang][action]}
                  </button>
                ))}
              </div>
            )}
            {m.moreOffset !== undefined && (
              <button className="tsw-more" onClick={() => showDeals(m.moreOffset!, m.id, m.dealsMaxPrice)} disabled={busy}>{t.more}</button>
            )}
            {m.siteUrl && <a className="tsw-site" href={m.siteUrl} target="_blank" rel="noopener">{t.all}</a>}
          </div>
        ))}
      </div>

      <div className="tsw-quick">
        <button className="tsw-deals" onClick={() => showDeals(0)} disabled={busy}>{t.deals}</button>
      </div>

      <form className="tsw-form" onSubmit={onSubmit} autoComplete="off">
        <input ref={photoInput} type="file" accept={PHOTO_TYPES.join(',')} hidden onChange={onPhotoChosen} />
        <button type="button" className="tsw-photo-btn" onClick={() => photoInput.current?.click()}
                disabled={busy} aria-label={PHOTO_TEXT[lang].button} title={PHOTO_TEXT[lang].button}>📷</button>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.placeholder} maxLength={300} />
        <button type="submit" disabled={busy || !input.trim()}>{t.send}</button>
      </form>
    </div>
  )
}