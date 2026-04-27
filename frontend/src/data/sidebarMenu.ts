import type { SidebarMenuItem } from '../types/catalog'

export const sidebarMenu: SidebarMenuItem[] = [
  {
    label: 'Maquinaria',
    to: '/catalogo?product_type=machinery',
  },
  {
    label: 'Repuestos',
    to: '/catalogo?product_type=spare_part',
  },
  {
    label: 'Servicios',
    to: '/catalogo?product_type=service',
  },
]
