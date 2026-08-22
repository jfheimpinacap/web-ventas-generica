import { useAdminProductImageUrl } from '../../hooks/useAdminProductImageUrl'

interface Props {
  imageId: number
  alt: string
}

export function AdminProductImage({ imageId, alt }: Props) {
  const { url, isLoading, hasError } = useAdminProductImageUrl(imageId)

  if (!url) {
    return <div className="admin-image-placeholder" aria-label={hasError ? 'Imagen no disponible' : undefined} aria-busy={isLoading} />
  }

  return <img src={url} alt={alt} />
}
