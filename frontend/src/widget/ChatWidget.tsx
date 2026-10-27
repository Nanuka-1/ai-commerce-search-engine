import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getDeals, sendMessage } from './api'
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
    const isSearch = response.type === 'product_search' && items.length > 0
    const actions: Action[] = isSearch ? [...(results.has_more ? ['more' as Action] : []), 'new_search'] : []
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

  async function run(userText: string | null, request: () => Promise<ChatResponse>) {
    if (busy) return
    if (userText) add({ role: 'user', text: userText })
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
            <div className={`tsw-bubble ${m.kind ?? ''}`}><Linkified text={m.text} /></div>
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
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.placeholder} maxLength={300} />
        <button type="submit" disabled={busy || !input.trim()}>{t.send}</button>
      </form>
    </div>
  )
}