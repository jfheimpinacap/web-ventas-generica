import type { ReactNode } from 'react'

import { AdminEditorLayout } from './AdminEditorLayout'

interface ProductEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar: ReactNode
  formId: string
  submitLabel: string
  isSubmitting: boolean
}

export function ProductEditorLayout({ title, onBack, form, sidebar, formId, submitLabel, isSubmitting }: ProductEditorLayoutProps) {
  return (
    <AdminEditorLayout
      title={title}
      onBack={onBack}
      form={form}
      sidebar={sidebar}
      headerActions={
        <button type="submit" form={formId} className="btn btn--accent" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando...' : submitLabel}
        </button>
      }
    />
  )
}
