import { useEffect, useState } from 'react'

const ANALYSIS_MAX_SIDE = 288
const OUTPUT_SIZE = 128
const TRANSPARENT_ALPHA_MAX = 16
const NEAR_WHITE_MIN = 235
const CORNER_EMPTY_RATIO = 0.9
const CONTENT_PADDING_RATIO = 0.1
const MAX_ZOOM = 4
const MIN_USEFUL_ZOOM = 1.12

type PixelBuffer = Pick<ImageData, 'data' | 'width' | 'height'>

export type VisibleBounds = {
  x: number
  y: number
  width: number
  height: number
}

function isEmptyPixel(data: Uint8ClampedArray, offset: number) {
  return data[offset + 3] <= TRANSPARENT_ALPHA_MAX
    || (data[offset] >= NEAR_WHITE_MIN
      && data[offset + 1] >= NEAR_WHITE_MIN
      && data[offset + 2] >= NEAR_WHITE_MIN)
}

function isSafeCorner(
  pixels: PixelBuffer,
  startX: number,
  startY: number,
  sampleWidth: number,
  sampleHeight: number,
) {
  let emptyPixels = 0
  const sampledPixels = sampleWidth * sampleHeight

  for (let y = startY; y < startY + sampleHeight; y += 1) {
    for (let x = startX; x < startX + sampleWidth; x += 1) {
      if (isEmptyPixel(pixels.data, (y * pixels.width + x) * 4)) emptyPixels += 1
    }
  }

  return emptyPixels / sampledPixels >= CORNER_EMPTY_RATIO
}

function expandAndClampBounds(bounds: VisibleBounds, canvasWidth: number, canvasHeight: number) {
  const paddedWidth = Math.min(canvasWidth, bounds.width * (1 + CONTENT_PADDING_RATIO * 2))
  const paddedHeight = Math.min(canvasHeight, bounds.height * (1 + CONTENT_PADDING_RATIO * 2))
  const fullScale = Math.min(OUTPUT_SIZE / canvasWidth, OUTPUT_SIZE / canvasHeight)
  const paddedScale = Math.min(OUTPUT_SIZE / paddedWidth, OUTPUT_SIZE / paddedHeight)
  const expansion = Math.max(1, paddedScale / (fullScale * MAX_ZOOM))
  const width = Math.min(canvasWidth, paddedWidth * expansion)
  const height = Math.min(canvasHeight, paddedHeight * expansion)
  const centerX = bounds.x + bounds.width / 2
  const centerY = bounds.y + bounds.height / 2

  return {
    x: Math.max(0, Math.min(canvasWidth - width, centerX - width / 2)),
    y: Math.max(0, Math.min(canvasHeight - height, centerY - height / 2)),
    width,
    height,
  }
}

export function detectVisibleBounds(pixels: PixelBuffer): VisibleBounds | null {
  if (pixels.width <= 0 || pixels.height <= 0 || pixels.data.length < pixels.width * pixels.height * 4) {
    return null
  }

  const sampleWidth = Math.max(1, Math.ceil(pixels.width * 0.06))
  const sampleHeight = Math.max(1, Math.ceil(pixels.height * 0.06))
  const safeCorners = [
    isSafeCorner(pixels, 0, 0, sampleWidth, sampleHeight),
    isSafeCorner(pixels, pixels.width - sampleWidth, 0, sampleWidth, sampleHeight),
    isSafeCorner(pixels, 0, pixels.height - sampleHeight, sampleWidth, sampleHeight),
    isSafeCorner(
      pixels,
      pixels.width - sampleWidth,
      pixels.height - sampleHeight,
      sampleWidth,
      sampleHeight,
    ),
  ].filter(Boolean).length

  if (safeCorners < 3) return null

  let minX = pixels.width
  let minY = pixels.height
  let maxX = -1
  let maxY = -1

  for (let y = 0; y < pixels.height; y += 1) {
    for (let x = 0; x < pixels.width; x += 1) {
      if (isEmptyPixel(pixels.data, (y * pixels.width + x) * 4)) continue
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
  }

  if (maxX < minX || maxY < minY) return null

  const bounds = expandAndClampBounds(
    { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 },
    pixels.width,
    pixels.height,
  )
  const fullScale = Math.min(OUTPUT_SIZE / pixels.width, OUTPUT_SIZE / pixels.height)
  const croppedScale = Math.min(OUTPUT_SIZE / bounds.width, OUTPUT_SIZE / bounds.height)

  return croppedScale / fullScale >= MIN_USEFUL_ZOOM ? bounds : null
}

export function useNormalizedAdminThumbnail(sourceUrl: string | null, enabled: boolean) {
  const [normalized, setNormalized] = useState<{ sourceUrl: string; url: string } | null>(null)

  useEffect(() => {
    let active = true
    let normalizedUrl: string | null = null

    setNormalized(null)
    if (!enabled || !sourceUrl || typeof document === 'undefined' || typeof Image === 'undefined') {
      return () => undefined
    }

    const image = new Image()
    image.onload = () => {
      if (!active || image.naturalWidth <= 0 || image.naturalHeight <= 0) return

      try {
        const analysisScale = Math.min(1, ANALYSIS_MAX_SIDE / Math.max(image.naturalWidth, image.naturalHeight))
        const analysisWidth = Math.max(1, Math.round(image.naturalWidth * analysisScale))
        const analysisHeight = Math.max(1, Math.round(image.naturalHeight * analysisScale))
        const analysisCanvas = document.createElement('canvas')
        analysisCanvas.width = analysisWidth
        analysisCanvas.height = analysisHeight
        const analysisContext = analysisCanvas.getContext('2d', { willReadFrequently: true })
        if (!analysisContext) return

        analysisContext.drawImage(image, 0, 0, analysisWidth, analysisHeight)
        const bounds = detectVisibleBounds(analysisContext.getImageData(0, 0, analysisWidth, analysisHeight))
        if (!bounds) return

        const sourceX = bounds.x / analysisScale
        const sourceY = bounds.y / analysisScale
        const sourceWidth = bounds.width / analysisScale
        const sourceHeight = bounds.height / analysisScale
        const outputCanvas = document.createElement('canvas')
        outputCanvas.width = OUTPUT_SIZE
        outputCanvas.height = OUTPUT_SIZE
        const outputContext = outputCanvas.getContext('2d')
        if (!outputContext) return

        const outputScale = Math.min(OUTPUT_SIZE / sourceWidth, OUTPUT_SIZE / sourceHeight)
        const outputWidth = sourceWidth * outputScale
        const outputHeight = sourceHeight * outputScale
        outputContext.drawImage(
          image,
          sourceX,
          sourceY,
          sourceWidth,
          sourceHeight,
          (OUTPUT_SIZE - outputWidth) / 2,
          (OUTPUT_SIZE - outputHeight) / 2,
          outputWidth,
          outputHeight,
        )
        outputCanvas.toBlob((blob) => {
          if (!blob) return
          const url = URL.createObjectURL(blob)
          if (!active) {
            URL.revokeObjectURL(url)
            return
          }
          normalizedUrl = url
          setNormalized({ sourceUrl, url })
        }, 'image/png')
      } catch {
        // The authenticated source remains visible if decoding or canvas access fails.
      }
    }
    image.onerror = () => undefined
    image.src = sourceUrl

    return () => {
      active = false
      image.onload = null
      image.onerror = null
      if (normalizedUrl) URL.revokeObjectURL(normalizedUrl)
    }
  }, [enabled, sourceUrl])

  return normalized?.sourceUrl === sourceUrl ? normalized.url : sourceUrl
}
