import { useAdminProductImageUrl } from '../../hooks/useAdminProductImageUrl'
import { useNormalizedAdminThumbnail } from '../../hooks/useNormalizedAdminThumbnail'

interface Props {
  imageId: number
  alt: string
  normalizeWhitespace?: boolean
}

export function AdminProductImage({ imageId, alt, normalizeWhitespace = false }: Props) {
  const { url, isLoading, hasError } = useAdminProductImageUrl(imageId)
  const displayUrl = useNormalizedAdminThumbnail(url, normalizeWhitespace)

  if (!url) {
    return <div className="admin-image-placeholder" aria-label={hasError ? 'Imagen no disponible' : undefined} aria-busy={isLoading} />
  }

  return <img src={displayUrl ?? url} alt={alt} />
}
