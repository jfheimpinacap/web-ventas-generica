import type { SidebarMenuItem } from '../types/catalog'

export const sidebarMenu: SidebarMenuItem[] = [
  {
    label: 'Maquinaria',
    children: [
      { label: 'Elevadores tipo tijera' },
      { label: 'Brazos articulados' },
      { label: 'Manipuladores telescópicos' },
      { label: 'Alzahombres' },
    ],
  },
  {
    label: 'Repuestos',
    children: [
      { label: 'Baterías' },
      { label: 'Ruedas' },
      { label: 'Controles' },
      { label: 'Sensores' },
      { label: 'Filtros' },
      { label: 'Componentes hidráulicos' },
    ],
  },
  {
    label: 'Marcas',
    children: [{ label: 'Genie' }, { label: 'JLG' }, { label: 'Haulotte' }, { label: 'Skyjack' }],
  },
  {
    label: 'Servicios',
    children: [{ label: 'Venta' }, { label: 'Repuestos' }, { label: 'Asesoría' }, { label: 'Cotización' }],
  },
]
