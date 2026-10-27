import type { Action, ChatResponse, Lang, TickerData } from './types'

// Свой id на браузер — у каждого посетителя своя сессия разговора на сервере.
export function userId(): string {
  const make = () => 'web-' + Math.random().toString(36).slice(2, 10)
  try {
    let id = localStorage.getItem('ts_chat_user')
    if (!id) {
      id = make()
      localStorage.setItem('ts_chat_user', id)
    }
    return id
  } catch {
    const w = window as unknown as { __tsChatId?: string }
    return w.__tsChatId ?? (w.__tsChatId = make())
  }
}

// 26.10: action — нажатая кнопка («more» / «new_search»); обычное сообщение — без action
export async function sendMessage(message: string, locale: Lang, action?: Action): Promise<ChatResponse> {
  const res = await fetch('/chat/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId(), message, locale, limit: 5, offset: 0, action: action ?? null }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Кнопка «📉 დღის ფასდაკლებები» и «კიდევ 5»: подборка скидок пачками, без LLM
export async function getDeals(locale: Lang, offset: number, maxPrice?: number | null, limit = 5): Promise<ChatResponse> {
  const params = new URLSearchParams({ lang: locale, offset: String(offset), limit: String(limit), user_id: userId() })
  if (maxPrice) params.set('max_price', String(maxPrice))
  const res = await fetch(`/promo/deals?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Бегущая строка в шапке панели (сервер кэширует 10 минут)
export async function getTicker(locale: Lang): Promise<TickerData> {
  const res = await fetch(`/promo/ticker?lang=${locale}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}