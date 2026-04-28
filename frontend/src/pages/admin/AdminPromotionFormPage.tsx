import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { PromotionForm } from '../../components/admin/PromotionForm'
import { createPromotion, getAdminProducts, getAdminPromotion, updatePromotion } from '../../services/adminApi'
import type { ProductListItem, PromotionFormValues } from '../../types/catalog'

const INITIAL_VALUES: PromotionFormValues = {
  title: '',
  subtitle: '',
  product: null,
  image: null,
  button_text: '',
  button_url: '',
  is_active: true,
  order: 0,
  starts_at: null,
  ends_at: null,
}

export function AdminPromotionFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = Boolean(id)
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [initialValues, setInitialValues] = useState(INITIAL_VALUES)
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const productList = await getAdminProducts()
        setProducts(productList)
        if (id) {
          const item = await getAdminPromotion(Number(id))
          setInitialValues({
            title: item.title,
            subtitle: item.subtitle,
            product: item.product?.id ?? null,
            image: null,
            button_text: item.button_text,
            button_url: item.button_url,
            is_active: item.is_active,
            order: item.order,
            starts_at: item.starts_at,
            ends_at: item.ends_at,
          })
        }
      } catch {
        setError('No se pudo cargar el formulario de promoción.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [id])

  const handleSubmit = async (values: PromotionFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      if (id) await updatePromotion(Number(id), values)
      else await createPromotion(values)
      navigate('/admin/promociones')
    } catch {
      setError('No se pudo guardar la promoción.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return <AdminLayout><h1>{isEdit ? 'Editar promoción' : 'Nueva promoción'}</h1>{loading ? <p className="ui-note">Cargando formulario...</p> : <PromotionForm initialValues={initialValues} products={products} onSubmit={handleSubmit} submitLabel={isEdit ? 'Guardar cambios' : 'Crear promoción'} isSubmitting={isSubmitting} error={error} />}</AdminLayout>
}
