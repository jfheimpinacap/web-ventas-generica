import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { CategoryForm } from '../../components/admin/CategoryForm'
import { createCategory, getAdminCategories, getAdminCategory, updateCategory } from '../../services/adminApi'
import type { Category, CategoryFormValues } from '../../types/catalog'

const INITIAL_VALUES: CategoryFormValues = { name: '', slug: '', parent: null, description: '', is_active: true, order: 0 }

export function AdminCategoryFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = Boolean(id)
  const [categories, setCategories] = useState<Category[]>([])
  const [initialValues, setInitialValues] = useState(INITIAL_VALUES)
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const list = await getAdminCategories()
        setCategories(list)
        if (id) {
          const entity = await getAdminCategory(Number(id))
          setInitialValues({
            name: entity.name,
            slug: entity.slug,
            parent: entity.parent,
            description: entity.description,
            is_active: entity.is_active,
            order: entity.order,
          })
        }
      } catch {
        setError('No se pudo cargar el formulario de categoría.')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [id])

  const handleSubmit = async (values: CategoryFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      if (isEdit && id) await updateCategory(Number(id), values)
      else await createCategory(values)
      navigate('/admin/categorias')
    } catch {
      setError('No se pudo guardar la categoría.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AdminLayout>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}
      {!loading ? (
        <AdminEditorLayout
          title={isEdit ? 'Editar categoría' : 'Nueva categoría'}
          onBack={() => navigate('/admin/categorias')}
          form={
            <CategoryForm
              initialValues={initialValues}
              categories={categories.filter((item) => String(item.id) !== id)}
              onSubmit={handleSubmit}
              submitLabel={isEdit ? 'Guardar cambios' : 'Crear categoría'}
              isSubmitting={isSubmitting}
              error={error}
            />
          }
        />
      ) : null}
    </AdminLayout>
  )
}
