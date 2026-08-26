export interface OptimizedProductImage {
  file: File
  originalFileName: string
  originalSize: number
  width: number
  height: number
}

export const MAX_SOURCE_SIZE = 20 * 1024 * 1024
export const MAX_OUTPUT_SIZE = 4.5 * 1024 * 1024
export const MAX_IMAGE_DIMENSION = 12000
export const MAX_IMAGE_PIXELS = 50000000
export const MAX_OUTPUT_DIMENSION = 1920
export const MIN_LONG_SIDE = 640

const ALLOWED_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp'])
const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const MIME_TYPES_BY_EXTENSION: Record<string, ReadonlySet<string>> = {
  jpg: new Set(['image/jpeg']),
  jpeg: new Set(['image/jpeg']),
  png: new Set(['image/png']),
  webp: new Set(['image/webp']),
}
const WEBP_QUALITIES = [0.82, 0.74, 0.66, 0.58]
const MAX_RESIZE_ATTEMPTS = 8
const MAX_FILE_NAME_LENGTH = 80

export class ProductImageOptimizationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ProductImageOptimizationError'
  }
}

export function calculateContainedDimensions(width: number, height: number, maximum = MAX_OUTPUT_DIMENSION) {
  const scale = Math.min(1, maximum / width, maximum / height)
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

export function createSafeWebPFileName(originalName: string) {
  const withoutExtension = originalName.replace(/\.[^.]*$/, '')
  const base = withoutExtension
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, MAX_FILE_NAME_LENGTH - '.webp'.length)
  return `${base || 'producto'}.webp`
}

function validateSource(file: File) {
  const extension = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() ?? '' : ''
  if (file.size === 0) throw new ProductImageOptimizationError('El archivo está vacío.')
  if (file.size > MAX_SOURCE_SIZE) throw new ProductImageOptimizationError('El archivo original supera el máximo de 20 MB.')
  const mimeType = file.type.toLowerCase()
  if (!ALLOWED_EXTENSIONS.has(extension) || !ALLOWED_MIME_TYPES.has(mimeType) || !MIME_TYPES_BY_EXTENSION[extension]?.has(mimeType)) {
    throw new ProductImageOptimizationError('El archivo debe tener extensión y formato JPG, PNG o WebP válidos.')
  }
}

interface DecodedImage {
  source: CanvasImageSource
  width: number
  height: number
  release: () => void
}

async function decodeWithImageElement(file: File): Promise<DecodedImage> {
  const objectUrl = URL.createObjectURL(file)
  const image = new Image()
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('decode'))
      image.src = objectUrl
    })
    return { source: image, width: image.naturalWidth, height: image.naturalHeight, release: () => URL.revokeObjectURL(objectUrl) }
  } catch {
    URL.revokeObjectURL(objectUrl)
    throw new ProductImageOptimizationError('No fue posible decodificar la imagen seleccionada.')
  }
}

async function decodeImage(file: File): Promise<DecodedImage> {
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return { source: bitmap, width: bitmap.width, height: bitmap.height, release: () => bitmap.close() }
    } catch {
      // Some browsers expose createImageBitmap without supporting imageOrientation.
    }
  }
  return decodeWithImageElement(file)
}

function encodeWebP(canvas: HTMLCanvasElement, quality: number) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) return reject(new ProductImageOptimizationError('El navegador no pudo generar la imagen WebP.'))
      if (blob.type !== 'image/webp') return reject(new ProductImageOptimizationError('Este navegador no admite la conversión requerida a WebP.'))
      resolve(blob)
    }, 'image/webp', quality)
  })
}

export async function optimizeProductImage(file: File): Promise<OptimizedProductImage> {
  validateSource(file)
  let decoded: DecodedImage
  try {
    decoded = await decodeImage(file)
  } catch (error) {
    if (error instanceof ProductImageOptimizationError) throw error
    throw new ProductImageOptimizationError('No fue posible decodificar la imagen seleccionada.')
  }

  try {
    const { width: sourceWidth, height: sourceHeight } = decoded
    if (sourceWidth <= 0 || sourceHeight <= 0) throw new ProductImageOptimizationError('La imagen no tiene dimensiones válidas.')
    if (sourceWidth > MAX_IMAGE_DIMENSION || sourceHeight > MAX_IMAGE_DIMENSION || sourceWidth * sourceHeight > MAX_IMAGE_PIXELS) {
      throw new ProductImageOptimizationError('La imagen supera el límite de 12.000 px por lado o 50.000.000 de píxeles.')
    }

    let dimensions = calculateContainedDimensions(sourceWidth, sourceHeight)
    const canvas = document.createElement('canvas')
    for (let resizeAttempt = 0; resizeAttempt <= MAX_RESIZE_ATTEMPTS; resizeAttempt += 1) {
      canvas.width = dimensions.width
      canvas.height = dimensions.height
      const context = canvas.getContext('2d')
      if (!context) throw new ProductImageOptimizationError('El navegador no pudo preparar la optimización de la imagen.')
      context.clearRect(0, 0, canvas.width, canvas.height)
      context.drawImage(decoded.source, 0, 0, dimensions.width, dimensions.height)

      for (const quality of WEBP_QUALITIES) {
        const blob = await encodeWebP(canvas, quality)
        if (blob.size <= MAX_OUTPUT_SIZE) {
          return {
            file: new File([blob], createSafeWebPFileName(file.name), { type: 'image/webp', lastModified: file.lastModified }),
            originalFileName: file.name,
            originalSize: file.size,
            width: dimensions.width,
            height: dimensions.height,
          }
        }
      }

      const longSide = Math.max(dimensions.width, dimensions.height)
      if (resizeAttempt === MAX_RESIZE_ATTEMPTS || longSide <= MIN_LONG_SIDE) break
      const scale = Math.max(0.85, MIN_LONG_SIDE / longSide)
      dimensions = {
        width: Math.max(1, Math.round(dimensions.width * scale)),
        height: Math.max(1, Math.round(dimensions.height * scale)),
      }
    }
    throw new ProductImageOptimizationError('No fue posible reducir la imagen WebP al máximo de 4,5 MB.')
  } finally {
    decoded.release()
  }
}
