import type { ReactNode } from 'react'

interface AdminPageHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function AdminPageHeader({ title, description, actions, className = '' }: AdminPageHeaderProps) {
  return (
    <header className={`admin-page-header ${className}`.trim()}>
      <h1 className="admin-page-header__title">{title}</h1>
      {description ? <div className="admin-page-header__description">{description}</div> : null}
      {actions ? <div className="admin-page-header__actions">{actions}</div> : null}
    </header>
  )
}
