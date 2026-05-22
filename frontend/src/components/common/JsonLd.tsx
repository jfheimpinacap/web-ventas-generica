import { useEffect, useMemo } from 'react'

interface JsonLdProps {
  id: string
  data: Record<string, unknown>
}

function safeJsonStringify(value: unknown) {
  return JSON.stringify(value).replace(/</g, '\\u003c')
}

export function JsonLd({ id, data }: JsonLdProps) {
  const serialized = useMemo(() => safeJsonStringify(data), [data])

  useEffect(() => {
    const selector = `script[type="application/ld+json"][data-jsonld-id="${id}"]`
    let script = document.head.querySelector(selector) as HTMLScriptElement | null

    if (!script) {
      script = document.createElement('script')
      script.setAttribute('type', 'application/ld+json')
      script.setAttribute('data-jsonld-id', id)
      document.head.appendChild(script)
    }

    script.textContent = serialized

    return () => {
      script?.remove()
    }
  }, [id, serialized])

  return null
}
