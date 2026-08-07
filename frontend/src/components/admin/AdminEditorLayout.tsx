import type { ReactNode } from 'react'

interface AdminEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar?: ReactNode
  headerActions?: ReactNode
  hideDefaultBackAction?: boolean
}

export function AdminEditorLayout({ title, onBack, form, sidebar, headerActions, hideDefaultBackAction = false }: AdminEditorLayoutProps) {
  return (
    <>
      <div className="admin-products-header">
        <h1>{title}</h1>
        <div className="admin-editor-header__actions">
          {!hideDefaultBackAction ? (
            <button type="button" className="btn btn--ghost" onClick={onBack}>
              Volver al listado
            </button>
          ) : null}
          {headerActions}
        </div>
      </div>

      <section className={`admin-edit-layout ${sidebar ? '' : 'admin-edit-layout--single'}`.trim()}>
        <div className="admin-edit-layout__form">{form}</div>
        {sidebar ? <aside className="admin-edit-layout__side">{sidebar}</aside> : null}
      </section>
    </>
  )
}
