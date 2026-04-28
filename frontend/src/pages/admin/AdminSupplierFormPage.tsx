import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { SupplierForm } from '../../components/admin/SupplierForm'
import { createSupplier, getAdminSupplier, updateSupplier } from '../../services/adminApi'
import type { SupplierFormValues } from '../../types/catalog'

const INITIAL_VALUES: SupplierFormValues = {
  name: '',
  contact_name: '',
  phone: '',
  email: '',
  notes: '',
  is_active: true,
}

export function AdminSupplierFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = Boolean(id)
  const [initialValues, setInitialValues] = useState(INITIAL_VALUES)
  const [loading, setLoading] = useState(isEdit)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    const load = async () => {
      try {
        const item = await getAdminSupplier(Number(id))
        setInitialValues({
          name: item.name,
          contact_name: item.contact_name,
          phone: item.phone,
          email: item.email,
          notes: item.notes,
          is_active: item.is_active,
        })
      } catch {
        setError('No se pudo cargar el proveedor.')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [id])

  const handleSubmit = async (values: SupplierFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      if (id) await updateSupplier(Number(id), values)
      else await createSupplier(values)
      navigate('/admin/proveedores')
    } catch {
      setError('No se pudo guardar el proveedor.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return <AdminLayout><h1>{isEdit ? 'Editar proveedor' : 'Nuevo proveedor'}</h1>{loading ? <p className="ui-note">Cargando formulario...</p> : <SupplierForm initialValues={initialValues} onSubmit={handleSubmit} submitLabel={isEdit ? 'Guardar cambios' : 'Crear proveedor'} isSubmitting={isSubmitting} error={error} />}</AdminLayout>
}
