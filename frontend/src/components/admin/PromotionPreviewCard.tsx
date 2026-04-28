interface PromotionPreviewCardProps {
  title: string
  subtitle: string
  productName?: string | null
  imageUrl?: string | null
  buttonText: string
  isActive: boolean
  order: number
}

const FALLBACK_PROMOTION_IMAGE = 'https://placehold.co/960x560/0f172a/e2e8f0?text=Vista+previa+de+promocion'

export function PromotionPreviewCard({
  title,
  subtitle,
  productName,
  imageUrl,
  buttonText,
  isActive,
  order,
}: PromotionPreviewCardProps) {
  return (
    <article className="admin-promo-preview" aria-label="Vista previa de promoción">
      <div className="admin-promo-preview__media">
        <img src={imageUrl || FALLBACK_PROMOTION_IMAGE} alt={title || 'Vista previa de promoción'} />
      </div>
      <div className="admin-promo-preview__overlay" />
      <div className="admin-promo-preview__content">
        <div className="admin-promo-preview__meta">
          <span className={`badge ${isActive ? 'badge--ok' : 'badge--muted'}`}>{isActive ? 'Activa' : 'Inactiva'}</span>
          <span className="admin-promo-preview__order">Orden #{order}</span>
        </div>
        <h3>{title.trim() || 'Título de la promoción'}</h3>
        <p>{subtitle.trim() || 'Subtítulo o mensaje comercial de apoyo para la promoción.'}</p>
        {productName ? <p className="admin-promo-preview__product">Producto asociado: {productName}</p> : null}
        <button type="button" className="btn btn--accent" disabled>
          {buttonText.trim() || 'Ver promoción'}
        </button>
      </div>
    </article>
  )
}
