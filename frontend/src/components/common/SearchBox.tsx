import { useState } from 'react'

interface SearchBoxProps {
  placeholder?: string
  onSearch?: (term: string) => void
}

export function SearchBox({ placeholder = 'Buscar maquinaria, repuestos o marca...', onSearch }: SearchBoxProps) {
  const [value, setValue] = useState('')

  return (
    <form
      className="search-box"
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
    </form>
  )
}
