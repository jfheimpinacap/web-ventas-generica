import type { ReactNode } from 'react'

import { AdminEditorLayout } from './AdminEditorLayout'
import { ProductEditorActions } from './ProductEditorActions'

interface ProductEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar: ReactNode
  formId: string
  isSubmitting: boolean
  showHeaderActions?: boolean
  submitBlocked?: boolean
}

export function ProductEditorLayout({ title, onBack, form, sidebar, formId, isSubmitting, showHeaderActions = true, submitBlocked = false }: ProductEditorLayoutProps) {
  return (
    <AdminEditorLayout
      title={title}
      onBack={onBack}
      form={form}
      sidebar={sidebar}
      hideDefaultBackAction
      headerActions={showHeaderActions ? (
        <ProductEditorActions formId={formId} isSubmitting={isSubmitting} onCancel={onBack} submitControl submitBlocked={submitBlocked} />
      ) : undefined}
    />
  )
}
