import { useEffect, useState } from 'react'
import { getTicker } from './api'
import type { Lang, TickerData } from './types'

function formatPrice(value: number): string {
  return (Number.isInteger(value) ? value : value.toFixed(2)) + ' ₾'
}

// Бегущая строка под шапкой: свежие снижения цен (или топ скидок — как решит promo.json).
// Медленно едет справа налево, при наведении останавливается, клик — страница товара на сайте.
export default function Ticker({ lang }: { lang: Lang }) {
  const [data, setData] = useState<TickerData | null>(null)

  useEffect(() => {
    let alive = true
    getTicker(lang)
      .then((ticker) => { if (alive) setData(ticker) })
      .catch(() => { if (alive) setData(null) })      // строка — бонус: нет данных → просто не показываем
    return () => { alive = false }
  }, [lang])

  const items = data?.items ?? []
  if (items.length === 0) return null

  const day = data?.since ? `${data.since.slice(8, 10)}.${data.since.slice(5, 7)}` : null
  const sinceText = day ? (lang === 'ka' ? `${day}-დან` : `since ${day}`) : null
  const loop = [...items, ...items]      // два круга подряд — лента едет без «прыжка»

  return (
    <div className="tsw-ticker">
      <div className="tsw-ticker-label">
        <span>{data?.title}</span>
        {sinceText && <small>{sinceText}</small>}
      </div>
      <div className="tsw-ticker-window">
        <div className="tsw-ticker-track" style={{ animationDuration: `${Math.max(items.length, 3) * 5}s` }}>
          {loop.map((item, i) => {
            const price = item.price ?? null
            const old = item.regular_price ?? item.old_price ?? null
            const off = price && old && old > price ? Math.round((1 - price / old) * 100) : 0
            return (
              <a key={i} className="tsw-tick" href={item.product_url} target="_blank" rel="noopener"
                 title={item.name} aria-hidden={i >= items.length} tabIndex={i >= items.length ? -1 : 0}>
                {item.image_url ? <img src={item.image_url} alt="" loading="lazy" /> : <span className="tsw-tick-noimg">👟</span>}
                <span className="tsw-tick-text">
                  {price !== null && <span className="tsw-tick-price">{formatPrice(price)}</span>}
                  {off > 0 && old && <span className="tsw-tick-old">{formatPrice(old)}</span>}
                </span>
                {off > 0 && <span className="tsw-tick-off">-{off}%</span>}
              </a>
            )
          })}
        </div>
      </div>
    </div>
  )
}
