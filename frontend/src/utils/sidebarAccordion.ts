import type { SidebarMenuItem } from '../types/catalog'

export interface SidebarAccordionState {
  openSection: string | null
  categoryPath: string[]
  initialCategoryId: string | null
  categoriesInitialized: boolean
}

type SidebarAccordionAction =
  | { type: 'toggleSection'; key: string }
  | { type: 'toggleCategory'; path: string[] }
  | { type: 'initializeCategories'; items: SidebarMenuItem[]; categoryId?: string | null }

export function createSidebarAccordionState(initialCategoryId: string | null): SidebarAccordionState {
  return { openSection: 'categories', categoryPath: [], initialCategoryId, categoriesInitialized: false }
}

export function sidebarMenuKey(item: SidebarMenuItem) {
  return item.to ?? item.label
}

export function sidebarCategoryId(item: SidebarMenuItem) {
  return item.to?.match(/[?&]category=(\d+)/)?.[1] ?? null
}

function findCategoryPath(items: SidebarMenuItem[], categoryId: string | null, ancestors: string[] = []): string[] | null {
  if (!categoryId) return null
  for (const item of items) {
    const path = [...ancestors, sidebarMenuKey(item)]
    if (sidebarCategoryId(item) === categoryId) return item.children?.length ? path : ancestors
    const found = findCategoryPath(item.children ?? [], categoryId, path)
    if (found) return found
  }
  return null
}

export function sidebarAccordionReducer(state: SidebarAccordionState, action: SidebarAccordionAction): SidebarAccordionState {
  switch (action.type) {
    case 'toggleSection':
      return { ...state, openSection: state.openSection === action.key ? null : action.key }
    case 'toggleCategory': {
      const isOpen = action.path.every((key, index) => state.categoryPath[index] === key)
      return {
        ...state,
        categoryPath: isOpen ? action.path.slice(0, -1) : action.path,
        categoriesInitialized: true,
      }
    }
    case 'initializeCategories':
      // Async category loading may initialize the entry route once, never override user choices.
      if (state.categoriesInitialized) return state
      return {
        ...state,
        categoryPath: findCategoryPath(action.items, action.categoryId ?? state.initialCategoryId) ?? [],
        categoriesInitialized: true,
      }
  }
}

export function sidebarCategoryHref(item: SidebarMenuItem, pathname: string, search: string) {
  const categoryId = sidebarCategoryId(item)
  if (!categoryId) return item.to
  const next = new URLSearchParams(search)
  next.set('category', categoryId)
  next.delete('product_type')
  return `${pathname}?${next.toString()}`
}
