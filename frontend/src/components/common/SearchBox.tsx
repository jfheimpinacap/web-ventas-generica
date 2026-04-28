import { useState } from 'react'
import { Link } from 'react-router-dom'

interface SearchBoxProps {
  placeholder?: string
  onSearch?: (term: string) => void
  className?: string
  showCatalogButton?: boolean
}

export function SearchBox({
  placeholder = 'Buscar maquinaria, repuestos o marca...',
  onSearch,
  className,
  showCatalogButton = false,
}: SearchBoxProps) {
  const [value, setValue] = useState('')

  return (
    <form
      className={['search-box', className].filter(Boolean).join(' ')}
      role="search"
      onSubmit={(event) => {
        event.preventDefault()
        onSearch?.(value.trim())
      }}
    >
      <input
        type="search"
        placeholder={placeholder}
        aria-label="Buscar en el catálogo"
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit">Buscar</button>
      {showCatalogButton ? (
        <Link className="btn btn--ghost search-box__catalog" to="/catalogo">
          Catálogo
        </Link>
      ) : null}
    </form>
  )
}
