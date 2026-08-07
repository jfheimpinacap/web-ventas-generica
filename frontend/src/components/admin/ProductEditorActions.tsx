interface ProductEditorActionsProps {
  formId: string
  isSubmitting: boolean
  onCancel: () => void
  submitControl?: boolean
}

export function ProductEditorActions({ formId, isSubmitting, onCancel, submitControl = false }: ProductEditorActionsProps) {
  const requestSubmit = () => {
    const form = document.getElementById(formId)
    if (form instanceof HTMLFormElement) form.requestSubmit()
  }

  return (
    <div className="admin-product-actions">
      <button
        type={submitControl ? 'submit' : 'button'}
        form={submitControl ? formId : undefined}
        className="btn btn--accent"
        disabled={isSubmitting}
        onClick={submitControl ? undefined : requestSubmit}
      >
        <svg className="admin-product-actions__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
          <path d="M17 21v-8H7v8M7 3v5h8" />
        </svg>
        {isSubmitting ? 'Guardando…' : 'Guardar producto'}
      </button>
      <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={isSubmitting}>
        <svg className="admin-product-actions__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m12 19-7-7 7-7M19 12H5" />
        </svg>
        Cancelar
      </button>
    </div>
  )
}
