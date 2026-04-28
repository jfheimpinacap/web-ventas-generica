import type { ReactNode } from 'react'

import { AdminEditorLayout } from './AdminEditorLayout'

interface ProductEditorLayoutProps {
  title: string
  onBack: () => void
  form: ReactNode
  sidebar: ReactNode
}

export function ProductEditorLayout({ title, onBack, form, sidebar }: ProductEditorLayoutProps) {
  return <AdminEditorLayout title={title} onBack={onBack} form={form} sidebar={sidebar} />
}
