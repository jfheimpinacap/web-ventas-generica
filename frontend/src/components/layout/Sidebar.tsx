import { useState } from 'react'

import { sidebarMenu } from '../../data/sidebarMenu'
import { SearchBox } from '../common/SearchBox'
import { SidebarMenu } from './SidebarMenu'

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
      <button className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen((prev) => !prev)}>
        {isOpen ? 'Cerrar menú' : 'Explorar categorías'}
      </button>

      <div className="sidebar__panel">
        <SearchBox />
        <SidebarMenu items={sidebarMenu} />
      </div>
    </aside>
  )
}
