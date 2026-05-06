import { Link } from 'react-router-dom'

export interface BreadcrumbItem {
  label: string
  to?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
  ariaLabel?: string
  className?: string
}

export function Breadcrumb({ items, ariaLabel = 'Ruta de navegación', className = '' }: BreadcrumbProps) {
  return (
    <nav className={`catalog-breadcrumb${className ? ` ${className}` : ''}`} aria-label={ariaLabel}>
      <ol className="catalog-breadcrumb__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1
          return (
            <li className="catalog-breadcrumb__item" key={`${item.label}-${index}`}>
              {item.to ? (
                <Link className="catalog-breadcrumb__link" to={item.to} aria-current={isLast ? 'page' : undefined}>
                  {item.label}
                </Link>
              ) : (
                <span className="catalog-breadcrumb__current" aria-current={isLast ? 'page' : undefined}>
                  {item.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
