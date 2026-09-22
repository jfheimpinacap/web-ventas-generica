import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { CategoryForm } from '../../components/admin/CategoryForm'
import { createCategory, getAdminCategories, getAdminCategory, updateCategory } from '../../services/adminApi'
import { useToast } from '../../toasts/ToastContext'
import { ADMIN_TOASTS } from '../../toasts/adminToastMessages'
import type { Category, CategoryFormValues } from '../../types/catalog'

const INITIAL_VALUES: CategoryFormValues = { name: '', slug: '', parent: null, product_type: 'machinery', description: '', is_active: true, order: 0 }

export function AdminCategoryFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [searchParams] = useSearchParams()
  const requestedParentId = Number(searchParams.get('parent')) || null
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
        if (!id && requestedParentId) {
          const parent = list.find((item) => item.id === requestedParentId)
          setInitialValues({ ...INITIAL_VALUES, parent: requestedParentId, product_type: parent?.product_type ?? 'machinery' })
        }
        if (id) {
          const entity = await getAdminCategory(Number(id))
          setInitialValues({
            name: entity.name,
            slug: entity.slug,
            parent: entity.parent,
            product_type: entity.product_type,
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
  }, [id, requestedParentId])

  const handleSubmit = async (values: CategoryFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      if (isEdit && id) await updateCategory(Number(id), values)
      else await createCategory(values)
      toast.success(isEdit ? ADMIN_TOASTS.category.update.success : ADMIN_TOASTS.category.create.success)
      navigate('/admin/categorias')
    } catch {
      toast.error(isEdit ? ADMIN_TOASTS.category.update.error : ADMIN_TOASTS.category.create.error)
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
              onSubmit={handleSubmit}
              submitLabel={isEdit ? 'Guardar cambios' : 'Crear categoría'}
              isSubmitting={isSubmitting}
              error={error}
              parentName={categories.find((item) => item.id === initialValues.parent)?.name ?? null}
              categories={categories}
              currentCategoryId={id ? Number(id) : null}
            />
          }
        />
      ) : null}
    </AdminLayout>
  )
}
