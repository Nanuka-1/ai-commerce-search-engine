import type { Lang } from './types'

// Тексты интерфейса виджета (ответы чата приходят с сервера уже на нужном языке).
export const UI: Record<Lang, Record<string, string>> = {
  ka: {
    title: 'AI ასისტენტი',
    hello: 'გამარჯობა! რით შემიძლია დაგეხმაროთ? 👋',
    placeholder: 'მაგ.: სარბენი ფეხსაცმელი 42',
    send: 'გაგზავნა',
    typing: 'ვეძებ…',
    view: 'საიტზე ნახვა',
    stockTip: 'მარაგი ფილიალებში — ღილაკი „მაღაზიებში შემოწმება“ პროდუქტის გვერდზე',
    all: 'ყველა ვარიანტი საიტზე →',
    ai: '✨ AI პასუხი',
    error: 'კავშირის შეცდომა. სცადეთ ხელახლა.',
    deals: '📉 დღის ფასდაკლებები',
    more: 'კიდევ 5 ↓',
    open: 'ჩატის გახსნა',
    close: 'დახურვა',
  },
  en: {
    title: 'AI assistant',
    hello: 'Hello! How can I help you? 👋',
    placeholder: 'e.g. running shoes 42',
    send: 'Send',
    typing: 'Searching…',
    view: 'View on site',
    stockTip: 'Store availability — “Check in stores” button on the product page',
    all: 'All options on the website →',
    ai: '✨ AI answer',
    error: 'Connection error. Please try again.',
    deals: '📉 Today’s deals',
    more: '5 more ↓',
    open: 'Open chat',
    close: 'Close',
  },
}
