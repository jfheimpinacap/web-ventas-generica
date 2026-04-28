import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { BrandForm } from '../../components/admin/BrandForm'
import { createBrand, getAdminBrand, updateBrand } from '../../services/adminApi'
import type { BrandFormValues } from '../../types/catalog'

const INITIAL_VALUES: BrandFormValues = { name: '', slug: '', description: '', logo: null, is_active: true }

export function AdminBrandFormPage() {
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
        const item = await getAdminBrand(Number(id))
        setInitialValues({ name: item.name, slug: item.slug, description: item.description, logo: null, is_active: item.is_active })
      } catch {
        setError('No se pudo cargar la marca.')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [id])

  const handleSubmit = async (values: BrandFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      if (id) await updateBrand(Number(id), values)
      else await createBrand(values)
      navigate('/admin/marcas')
    } catch {
      setError('No se pudo guardar la marca.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return <AdminLayout><h1>{isEdit ? 'Editar marca' : 'Nueva marca'}</h1>{loading ? <p className="ui-note">Cargando formulario...</p> : <BrandForm initialValues={initialValues} onSubmit={handleSubmit} submitLabel={isEdit ? 'Guardar cambios' : 'Crear marca'} isSubmitting={isSubmitting} error={error} />}</AdminLayout>
}
