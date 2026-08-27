import { useEffect, useRef, useState } from 'react'

import { trackShare } from '../../utils/analytics'
import { buildPublicUrl } from '../../utils/seo'

interface ShareButtonProps { slug: string; title: string; text?: string; productType: string }

export function ShareButton({ slug, title, text, productType }: ShareButtonProps) {
  const [status, setStatus] = useState('')
  const [fallbackUrl, setFallbackUrl] = useState('')
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; setStatus(''); setFallbackUrl(''); return () => { mounted.current = false } }, [slug])

  const copyOrShow = async (url: string) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(url)
      if (!mounted.current) return
      setStatus('Enlace copiado')
      trackShare({ method: 'clipboard', content_type: 'product', product_name: title, product_type: productType, location: 'product_detail' })
    } catch {
      if (mounted.current) { setStatus('No fue posible copiar automáticamente. Selecciona y copia el enlace.'); setFallbackUrl(url) }
    }
  }

  const onShare = async () => {
    const url = buildPublicUrl(`/producto/${encodeURIComponent(slug)}`)
    setStatus(''); setFallbackUrl('')
    if (navigator.share) {
      try {
        await navigator.share({ title, text: text?.trim() || undefined, url })
        if (!mounted.current) return
        setStatus('Producto compartido')
        trackShare({ method: 'web_share', content_type: 'product', product_name: title, product_type: productType, location: 'product_detail' })
        return
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
      }
    }
    await copyOrShow(url)
  }

  return <div className="share-product">
    <button className="btn btn--ghost" type="button" onClick={() => void onShare()}>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 10.5 6.8-4M8.6 13.5l6.8 4"/></svg>
      Compartir
    </button>
    {status ? <p className={fallbackUrl ? 'ui-note ui-note--error' : 'ui-note'} role={fallbackUrl ? undefined : 'status'}>{status}</p> : null}
    {fallbackUrl ? <label className="share-product__fallback">Enlace del producto<input readOnly value={fallbackUrl} onFocus={(event) => event.currentTarget.select()} /></label> : null}
  </div>
}
