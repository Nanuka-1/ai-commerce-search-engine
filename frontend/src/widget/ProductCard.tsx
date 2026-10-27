import type { Product } from './types'

// Ссылка на товар сразу с размером клиента: сайт откроется на нужном размере,
// там же кнопка «მაღაზიებში შემოწმება» — наличие по филиалам (это знает только сайт).
function withSize(url: string, size?: string | null, sizes: string[] = []): string {
  if (!size || !sizes.map(String).includes(String(size))) return url
  try {
    const link = new URL(url)
    link.searchParams.set('size', String(size))
    return link.toString()
  } catch {
    return url
  }
}

function formatPrice(value: number): string {
  return (Number.isInteger(value) ? value : value.toFixed(2)) + ' ₾'
}

// Карточка товара — только данные с сервера (цена, размеры, ссылка). Компактная — под узкую панель.
export default function ProductCard({ item, askedSize, viewText, stockTip }:
  { item: Product; askedSize?: string | null; viewText: string; stockTip?: string }) {
  const price = item.price_from ?? item.price ?? null
  const old = item.regular_price ?? item.old_price ?? null          // «было»: зачёркнутая цена сайта или до снижения
  const off = price && old && old > price ? Math.round((1 - price / old) * 100) : 0
  const sizes = item.sizes ?? (item.size ? [item.size] : [])

  return (
    <div className="tsw-card">
      <div className="tsw-card-img">
        {item.image_url ? <img src={item.image_url} alt={item.name ?? ''} loading="lazy" /> : <span>👟</span>}
        {off > 0 && <span className="tsw-off">-{off}%</span>}
        {item.scarce_label && <span className="tsw-scarce">{item.scarce_label}</span>}
      </div>
      <div className="tsw-card-body">
        {item.brand && <div className="tsw-brand">{item.brand}</div>}
        <div className="tsw-name" title={item.name}>{item.name}</div>
        <div className="tsw-price">
          {price !== null && <span className="tsw-now">{formatPrice(price)}</span>}
          {off > 0 && old && <span className="tsw-old">{formatPrice(old)}</span>}
        </div>
        {sizes.length > 0 && (
          <div className="tsw-sizes">
            {sizes.slice(0, 8).map((s) => (
              <span key={s} className={String(s) === String(askedSize) ? 'hit' : ''}>{s}</span>
            ))}
          </div>
        )}
        {item.product_url && (
          <a className="tsw-go" href={withSize(item.product_url, askedSize, sizes)} target="_blank" rel="noopener"
             title={stockTip}>{viewText}</a>
        )}
      </div>
    </div>
  )
}
