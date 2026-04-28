import type { ReactNode } from 'react'

interface ProductEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar: ReactNode
}

export function ProductEditorLayout({ title, onBack, form, sidebar }: ProductEditorLayoutProps) {
  return (
    <>
      <div className="admin-products-header">
        <h1>{title}</h1>
        <button type="button" className="btn btn--ghost" onClick={onBack}>
          Volver
        </button>
      </div>

      <section className="admin-edit-layout">
        <div className="admin-edit-layout__form">{form}</div>
        <aside className="admin-edit-layout__side">{sidebar}</aside>
      </section>
    </>
  )
}
