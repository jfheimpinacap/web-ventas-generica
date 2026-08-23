import { useCallback, useEffect, useRef, useState } from 'react'
import { optimizeProductImage } from '../utils/productImageOptimizer'

export type PendingImageStatus = 'pending' | 'uploading' | 'error'

export interface PendingProductImage {
  id: string
  file: File
  previewUrl: string
  altText: string
  status: PendingImageStatus
  error: string | null
  originalFileName: string
  originalSize: number
  width: number
  height: number
}
let imageSequence = 0

function revokeAfterRender(previewUrl: string) {
  window.setTimeout(() => URL.revokeObjectURL(previewUrl), 0)
}

export function usePendingProductImages() {
  const [images, setImages] = useState<PendingProductImage[]>([])
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processingMessage, setProcessingMessage] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const processingRef = useRef(false)
  const imagesRef = useRef(images)
  imagesRef.current = images

  useEffect(() => () => {
    mountedRef.current = false
    imagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl))
  }, [])

  const addFiles = useCallback(async (files: File[]): Promise<void> => {
    if (processingRef.current || files.length === 0) return
    processingRef.current = true
    setIsProcessing(true)
    setSelectionError(null)
    const failures: string[] = []
    for (let index = 0; index < files.length; index += 1) {
      if (!mountedRef.current) break
      setProcessingMessage(`Optimizando ${index + 1} de ${files.length} imágenes…`)
      try {
        const optimized = await optimizeProductImage(files[index])
        const previewUrl = URL.createObjectURL(optimized.file)
        if (!mountedRef.current) {
          URL.revokeObjectURL(previewUrl)
          break
        }
        setImages((current) => [...current, {
          id: `pending-image-${Date.now()}-${imageSequence++}`,
          ...optimized,
          previewUrl,
          altText: '',
          status: 'pending',
          error: null,
        }])
      } catch (error) {
        const reason = error instanceof Error ? error.message : 'No fue posible optimizar el archivo.'
        failures.push(`${files[index].name}: ${reason}`)
      }
    }
    processingRef.current = false
    if (mountedRef.current) {
      setSelectionError(failures.length ? `No se incorporaron ${failures.length === 1 ? '1 archivo' : `${failures.length} archivos`}: ${failures.join(' ')}` : null)
      setProcessingMessage(null)
      setIsProcessing(false)
    }
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

  return { images, addFiles, removeImage, updateImage, removeSuccessfulImages, clearImages, selectionError, isProcessing, processingMessage }
}
