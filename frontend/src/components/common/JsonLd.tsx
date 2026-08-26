import { useEffect, useMemo } from 'react'

interface JsonLdProps {
  id: string
  data: Record<string, unknown>
}

export function safeJsonStringify(value: unknown) {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

export function JsonLd({ id, data }: JsonLdProps) {
  const serialized = useMemo(() => safeJsonStringify(data), [data])

  useEffect(() => {
    if (!/^[a-z0-9-]+$/.test(id)) return

    const matchingScripts = Array.from(document.head.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"][data-jsonld-id]'))
      .filter((candidate) => candidate.dataset.jsonldId === id)
    let script = matchingScripts.shift() ?? null
    matchingScripts.forEach((duplicate) => duplicate.remove())

    if (!script) {
      script = document.createElement('script')
      script.setAttribute('type', 'application/ld+json')
      script.setAttribute('data-jsonld-id', id)
      document.head.appendChild(script)
    }

    script.textContent = serialized

    return () => {
      if (script?.isConnected) script.remove()
    }
  }, [id, serialized])

  return null
}
