import { useEffect, useMemo, useRef, useState } from 'react'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { getSafeApiErrorMessage } from '../../services/api'
import { authBlobFetch } from '../../services/authApi'
import { createTechnicalSheet, deleteTechnicalSheet, getTechnicalSheets, renameTechnicalSheet, replaceTechnicalSheetFile } from '../../services/adminApi'
import type { TechnicalSheet } from '../../types/catalog'

const MAX_SIZE = 10 * 1024 * 1024

export function AdminTechnicalSheetsPage() {
  const [items, setItems] = useState<TechnicalSheet[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const replaceInput = useRef<HTMLInputElement>(null)
  const replacingId = useRef<number | null>(null)

  const load = async () => {
    try { setError(null); setItems(await getTechnicalSheets()) }
    catch (e) { setError(getSafeApiErrorMessage(e, 'No se pudieron cargar las fichas técnicas.')) }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])
  const filtered = useMemo(() => items.filter(x => x.name.toLowerCase().includes(search.trim().toLowerCase())), [items, search])

  const validateFile = (selected: File | null) => {
    if (!selected) return 'Selecciona un archivo.'
    const extension = selected.name.toLowerCase().match(/\.[^.]+$/)?.[0]
    const allowed: Record<string, string> = { '.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp' }
    if (!extension || allowed[extension] !== selected.type) return 'Selecciona un archivo PDF, JPG/JPEG, PNG o WebP válido; la extensión y el tipo deben coincidir.'
    if (!selected.size) return 'El archivo está vacío.'
    if (selected.size > MAX_SIZE) return 'El archivo no puede superar 10 MB.'
    return null
  }

  const submitCreate = async () => {
    const validation = !name.trim() ? 'Escribe un nombre para la ficha.' : validateFile(file)
    if (validation) { setError(validation); return }
    setBusy(true); setError(null)
    try {
      const created = await createTechnicalSheet(name.trim(), file!)
      setItems(current => [created, ...current]); setShowCreate(false); setName(''); setFile(null); setMessage('Ficha técnica agregada correctamente.')
    } catch (e) { setError(getSafeApiErrorMessage(e, 'No se pudo agregar la ficha técnica.')) }
    finally { setBusy(false) }
  }

  const editName = async (item: TechnicalSheet) => {
    const next = window.prompt('Nombre de la ficha técnica', item.name)
    if (next === null || next.trim() === item.name) return
    if (!next.trim()) { setError('El nombre es obligatorio.'); return }
    setBusy(true)
    try { const updated = await renameTechnicalSheet(item.id, next.trim()); setItems(xs => xs.map(x => x.id === item.id ? updated : x)); setMessage('Nombre actualizado.') }
    catch (e) { setError(getSafeApiErrorMessage(e, 'No se pudo cambiar el nombre.')) }
    finally { setBusy(false) }
  }

  const replace = async (selected: File | null) => {
    const id = replacingId.current; const validation = validateFile(selected)
    if (!id || validation) { if (validation) setError(validation); return }
    setBusy(true)
    try { const updated = await replaceTechnicalSheetFile(id, selected!); setItems(xs => xs.map(x => x.id === id ? updated : x)); setMessage('Archivo reemplazado correctamente.') }
    catch (e) { setError(getSafeApiErrorMessage(e, 'No se pudo reemplazar el archivo.')) }
    finally { setBusy(false); if (replaceInput.current) replaceInput.current.value = '' }
  }

  const remove = async (item: TechnicalSheet) => {
    if (!window.confirm(`¿Eliminar la ficha técnica "${item.name}"? Esta acción no se puede deshacer.`)) return
    setBusy(true)
    try { await deleteTechnicalSheet(item.id); setItems(xs => xs.filter(x => x.id !== item.id)); setMessage('Ficha técnica eliminada.') }
    catch (e) { setError(getSafeApiErrorMessage(e, 'No se pudo eliminar la ficha técnica.')) }
    finally { setBusy(false) }
  }

  const openFile = async (item: TechnicalSheet, download: boolean) => {
    try {
      setError(null)
      const blob = await authBlobFetch(item.file_url, download ? { download: true } : undefined)
      const objectUrl = URL.createObjectURL(blob)
      if (download) { const a = document.createElement('a'); a.href = objectUrl; a.download = item.original_file_name; a.click() }
      else window.open(objectUrl, '_blank', 'noopener,noreferrer')
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
    } catch (e) {
      setError(getSafeApiErrorMessage(e, download ? 'No se pudo descargar el archivo.' : 'No se pudo abrir el archivo.'))
    }
  }

  return <AdminLayout>
    <div className="admin-products-header"><div><h1>Fichas técnicas</h1><p className="ui-note">Administra archivos PDF, JPG/JPEG, PNG o WebP (máximo 10 MB) que podrás usar en tus productos.</p></div><button className="btn btn--accent" onClick={() => setShowCreate(true)}>Agregar ficha técnica</button></div>
    <div className="admin-list-toolbar"><input className="admin-search" placeholder="Buscar por nombre" value={search} onChange={e => setSearch(e.target.value)} /></div>
    {error ? <p className="ui-note ui-note--error">{error}</p> : null}{message ? <p className="ui-note">{message}</p> : null}
    {showCreate ? <section className="technical-sheet-form"><h2>Nueva ficha técnica</h2><label>Nombre<input value={name} maxLength={220} onChange={e => setName(e.target.value)} /></label><label>Archivo PDF, JPG/JPEG, PNG o WebP (máximo 10 MB)<input type="file" accept="application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>{file ? <p>Archivo seleccionado: {file.name}</p> : null}<div><button className="btn btn--accent" disabled={busy} onClick={() => void submitCreate()}>{busy ? 'Guardando...' : 'Guardar'}</button> <button className="btn" disabled={busy} onClick={() => setShowCreate(false)}>Cancelar</button></div></section> : null}
    {loading ? <p>Cargando fichas técnicas...</p> : !items.length ? <p>No hay fichas técnicas registradas.</p> : !filtered.length ? <p>No se encontraron fichas con ese nombre.</p> : <div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Nombre</th><th>Archivo</th><th>Tamaño</th><th>Actualizada</th><th>Acciones</th></tr></thead><tbody>{filtered.map(item => <tr key={item.id}><td>{item.name}</td><td>{item.original_file_name}</td><td>{formatBytes(item.size_bytes)}</td><td>{new Date(item.updated_at).toLocaleDateString('es-CL')}</td><td><button className="table-action table-action--button" disabled={busy} onClick={() => void openFile(item, false)}>Ver archivo</button>{' '}<button className="table-action table-action--button" disabled={busy} onClick={() => void openFile(item, true)}>Descargar</button>{' '}<button className="table-action table-action--button" disabled={busy} onClick={() => void editName(item)}>Editar</button>{' '}<button className="table-action table-action--button" disabled={busy} onClick={() => { replacingId.current = item.id; replaceInput.current?.click() }}>Reemplazar archivo</button>{' '}<button className="table-action table-action--button" disabled={busy} onClick={() => void remove(item)}>Eliminar</button></td></tr>)}</tbody></table></div>}
    <input ref={replaceInput} hidden type="file" accept="application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp" onChange={e => void replace(e.target.files?.[0] ?? null)} />
  </AdminLayout>
}

function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB` }
