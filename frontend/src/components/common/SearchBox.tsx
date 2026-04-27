interface SearchBoxProps {
  placeholder?: string
}

export function SearchBox({ placeholder = 'Buscar maquinaria, repuestos o marca...' }: SearchBoxProps) {
  return (
    <form className="search-box" role="search" onSubmit={(event) => event.preventDefault()}>
      <input type="search" placeholder={placeholder} aria-label="Buscar en el catálogo" />
      <button type="submit">Buscar</button>
    </form>
  )
}
