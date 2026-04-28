import type { ReactNode } from 'react'

interface AdminEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar?: ReactNode
}

export function AdminEditorLayout({ title, onBack, form, sidebar }: AdminEditorLayoutProps) {
  return (
    <>
      <div className="admin-products-header">
        <h1>{title}</h1>
        <button type="button" className="btn btn--ghost" onClick={onBack}>
          Volver al listado
        </button>
      </div>

      <section className={`admin-edit-layout ${sidebar ? '' : 'admin-edit-layout--single'}`.trim()}>
        <div className="admin-edit-layout__form">{form}</div>
        {sidebar ? <aside className="admin-edit-layout__side">{sidebar}</aside> : null}
      </section>
    </>
  )
}
