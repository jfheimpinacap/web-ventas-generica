import { useCallback, useEffect, useRef, useState } from 'react'

export type PendingImageStatus = 'pending' | 'uploading' | 'error'

export interface PendingProductImage {
  id: string
  file: File
  previewUrl: string
  altText: string
  status: PendingImageStatus
  error: string | null
}

const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
let imageSequence = 0

function revokeAfterRender(previewUrl: string) {
  window.setTimeout(() => URL.revokeObjectURL(previewUrl), 0)
}

function isAllowedImage(file: File) {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  return ALLOWED_EXTENSIONS.includes(extension) && ALLOWED_TYPES.includes(file.type.toLowerCase())
}

export function usePendingProductImages() {
  const [images, setImages] = useState<PendingProductImage[]>([])
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const imagesRef = useRef(images)
  imagesRef.current = images

  useEffect(() => () => {
    imagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl))
  }, [])

  const addFiles = useCallback((files: File[]) => {
    const validFiles = files.filter(isAllowedImage)
    const invalidCount = files.length - validFiles.length
    setSelectionError(invalidCount > 0
      ? `${invalidCount === 1 ? 'Un archivo no corresponde' : `${invalidCount} archivos no corresponden`} a los formatos JPG, PNG o WebP.`
      : null)
    if (validFiles.length === 0) return

    const additions = validFiles.map((file) => ({
      id: `pending-image-${Date.now()}-${imageSequence++}`,
      file,
      previewUrl: URL.createObjectURL(file),
      altText: '',
      status: 'pending' as const,
      error: null,
    }))
    setImages((current) => [...current, ...additions])
  }, [])

  const removeImage = useCallback((id: string) => {
    setImages((current) => {
      const removed = current.find((image) => image.id === id)
      if (removed) revokeAfterRender(removed.previewUrl)
      return current.filter((image) => image.id !== id)
    })
  }, [])

  const updateImage = useCallback((id: string, patch: Partial<Pick<PendingProductImage, 'altText' | 'status' | 'error'>>) => {
    setImages((current) => current.map((image) => image.id === id ? { ...image, ...patch } : image))
  }, [])

  const removeSuccessfulImages = useCallback((ids: Set<string>) => {
    setImages((current) => {
      current.filter((image) => ids.has(image.id)).forEach((image) => revokeAfterRender(image.previewUrl))
      return current.filter((image) => !ids.has(image.id))
    })
  }, [])

  const clearImages = useCallback(() => {
    setImages((current) => {
      current.forEach((image) => revokeAfterRender(image.previewUrl))
      return []
    })
  }, [])

  return { images, addFiles, removeImage, updateImage, removeSuccessfulImages, clearImages, selectionError }
}
