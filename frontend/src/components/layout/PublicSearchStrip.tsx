import { useNavigate } from 'react-router-dom'

import { SearchBox } from '../common/SearchBox'

interface PublicSearchStripProps {
  onSearch?: (term: string) => void
}

export function PublicSearchStrip({ onSearch }: PublicSearchStripProps) {
  const navigate = useNavigate()

  const handleSearch = (term: string) => {
    if (onSearch) {
      onSearch(term)
      return
    }

    navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')
  }

  return (
    <section className="public-search-strip" aria-label="Buscador principal">
      <div className="public-search-strip__inner">
        <SearchBox
          className="search-box--primary"
          placeholder="Busca maquinaria, repuestos y servicios"
          onSearch={handleSearch}
          showCatalogButton
        />
      </div>
    </section>
  )
}
