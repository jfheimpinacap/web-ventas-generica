import type { ReactNode } from 'react'

export type AdminIconName = 'box' | 'file' | 'folder' | 'tag' | 'truck' | 'clipboard' | 'megaphone' | 'star' | 'external' | 'logout' | 'menu' | 'close' | 'plus' | 'search' | 'reset' | 'edit' | 'download' | 'trash'

const paths: Record<AdminIconName, ReactNode> = {
  box: <><path d="m4 7.5 8-4 8 4-8 4-8-4Z" /><path d="M4 7.5v9l8 4 8-4v-9M12 11.5v9" /></>,
  file: <><path d="M6 2.5h8l4 4v15H6z" /><path d="M14 2.5v4h4M9 12h6M9 16h6" /></>,
  folder: <path d="M3 6.5h7l2 2h9v11H3z" />,
  tag: <><path d="M3 4h8l10 10-7 7L4 11z" /><circle cx="8" cy="8" r="1" /></>,
  truck: <><path d="M3 5h11v11H3zM14 9h4l3 4v3h-7z" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
  clipboard: <><path d="M7 5H4v17h16V5h-3" /><rect x="8" y="2" width="8" height="5" rx="1" /><path d="M8 12h8M8 16h8" /></>,
  megaphone: <><path d="m3 10 14-6v14L3 12zM7 13l2 7h4l-2-8M20 9v4" /></>,
  star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z" />,
  external: <><path d="M13 4h7v7M20 4 10 14" /><path d="M18 14v6H4V6h6" /></>,
  logout: <><path d="M10 4H4v16h6M14 8l4 4-4 4M8 12h10" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="m16 16 5 5" /></>,
  reset: <><path d="M4 7v5h5" /><path d="M5.5 16a8 8 0 1 0 .5-9l-2 5" /></>,
  edit: <><path d="m4 20 4.5-1 10-10-3.5-3.5-10 10z" /><path d="m13.5 7 3.5 3.5" /></>,
  download: <><path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 20h14" /></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6" /></>,
}

export function AdminIcon({ name }: { name: AdminIconName }) {
  return <svg className="admin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
