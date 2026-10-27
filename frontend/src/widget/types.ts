// Ответ нашего API (POST /chat/message). Поля — как в chat_use_case / response_builder.
export type Lang = 'ka' | 'en'

// 26.10: кнопки под карточками — команда серверу, а не текст
export type Action = 'more' | 'new_search'

export interface Product {
  name?: string
  brand?: string
  price?: number | null
  price_from?: number | null
  regular_price?: number | null
  old_price?: number | null        // «свежие скидки»: цена до снижения
  discount_percent?: number
  drop_percent?: number
  sizes?: string[]
  size?: string
  product_url?: string
  image_url?: string | null
  scarce_label?: string          // «🔥 დარჩა 2 ზომა» — реальный дефицит размеров на сайте (сервер)
}

export interface ChatResponse {
  type?: string
  message?: string
  data?: {
    results?: {
      query?: string
      items?: Product[]
      site_search_url?: string
      since?: string | null
      offset?: number
      limit?: number
      has_more?: boolean
      max_price?: number | null
    }
  }
  meta?: {
    ai_used?: boolean
    dialog_state?: string        // 26.10: понятые условия «ქალის · ფეხსაცმელი · 36 · ≤ 300 ₾»
  }
}

// GET /promo/ticker — бегущая строка (что показывать — app/config/promo.json)
export interface TickerData {
  title?: string
  sale_url?: string
  mode?: string
  since?: string | null          // fresh_drops: дата прогона скрапера «YYYY-MM-DD»
  items?: Product[]
}

export interface Message {
  id: number
  role: 'user' | 'bot'
  text: string
  items?: Product[]
  siteUrl?: string
  aiUsed?: boolean
  askedSize?: string | null
  kind?: 'typing' | 'error'
  moreOffset?: number            // подборка скидок: с какого места грузить «კიდევ 5»
  dealsMaxPrice?: number | null  // бюджет подборки — «კიდევ 5» продолжает с ним же
  conditions?: string            // 26.10: строка понятых условий над карточками
  actions?: Action[]             // 26.10: кнопки под карточками поиска
}