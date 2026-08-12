import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { AdminLayout } from "../../components/admin/AdminLayout";
import { ProductEditorLayout } from "../../components/admin/ProductEditorLayout";
import { ProductForm } from "../../components/admin/ProductForm";
import { ProductImageManager } from "../../components/admin/ProductImageManager";
import { ProductTechnicalData } from "../../components/catalog/ProductTechnicalData";
import { usePendingProductImages } from "../../hooks/usePendingProductImages";
import {
  createProductImage,
  createProductSpec,
  deleteProduct,
  deleteProductImage,
  deleteProductSpec,
  getAdminProduct,
  getProductImages,
  getProductSpecs,
  getTechnicalSheets,
  updateProduct,
  updateProductImage,
  updateProductSpec,
} from "../../services/adminApi";
import {
  getSafeApiErrorMessage,
  resolveMediaUrl,
} from "../../services/api";
import {
  getAdminBrands,
  getAdminCategories,
  getAdminSuppliers,
} from "../../services/adminApi";
import type {
  Brand,
  Category,
  ProductFormValues,
  ProductImage,
  ProductSpec,
  ProductSpecWritePayload,
  SupplierSummary,
  TechnicalSheet,
} from "../../types/catalog";
import {
  formatCondition,
  formatPriceValue,
  formatStockStatus,
} from "../../utils/formatters";

function mapProductToFormValues(
  product: Awaited<ReturnType<typeof getAdminProduct>>,
): ProductFormValues {
  return {
    name: product.name,
    category: product.category.id,
    brand: product.brand?.id ?? null,
    supplier: product.supplier?.id ?? null,
    technical_sheet: product.technical_sheet?.id ?? null,
    product_type: product.product_type,
    condition: product.condition,
    short_description: product.short_description,
    description: product.description,
    model: product.model,
    sku: product.sku,
    working_height_m: product.working_height_m,
    terrain_type: product.terrain_type,
    year: product.year,
    hours_meter: product.hours_meter,
    maximum_load_capacity_kg: product.maximum_load_capacity_kg,
    power_source: product.power_source,
    includes_technical_review: product.includes_technical_review,
    includes_commercial_technical_advice: product.includes_commercial_technical_advice,
    includes_coordinated_delivery: product.includes_coordinated_delivery,
    price: product.price,
    price_currency: product.price_currency ?? "CLP",
    price_tax_mode: product.price_tax_mode ?? "plus_vat",
    price_visible: product.price_visible,
    stock_status: product.stock_status,
    is_featured: product.is_featured,
    is_published: product.is_published,
  };
}

const initialSpecForm = {
  name: "",
  value: "",
  unit: "",
  order: 0,
};

const PLACEHOLDER_IMAGE =
  "https://placehold.co/600x400/111827/F3F4F6?text=Producto";
const PRODUCT_EDIT_FORM_ID = "admin-product-edit-form";

export function AdminProductEditPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();
  const [productId, setProductId] = useState<number | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [technicalSheets, setTechnicalSheets] = useState<TechnicalSheet[]>([]);
  const [initialValues, setInitialValues] = useState<ProductFormValues | null>(
    null,
  );
  const [formValues, setFormValues] = useState<ProductFormValues | null>(null);

  const [images, setImages] = useState<ProductImage[]>([]);
  const [specs, setSpecs] = useState<ProductSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const pending = usePendingProductImages();
  const [selectedPendingId, setSelectedPendingId] = useState<string | null>(null);
  const [imageSaving, setImageSaving] = useState(false);
  const [imageStatus, setImageStatus] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(() => {
    const state = location.state;
    return typeof state === "object" && state && "imageError" in state
      ? String(state.imageError)
      : null;
  });
  useEffect(() => {
    if (selectedPendingId && !pending.images.some((image) => image.id === selectedPendingId)) {
      setSelectedPendingId(null);
    }
  }, [pending.images, selectedPendingId]);

  const [specForm, setSpecForm] = useState(initialSpecForm);
  const [specSaving, setSpecSaving] = useState(false);
  const [specStatus, setSpecStatus] = useState<string | null>(null);
  const [specError, setSpecError] = useState<string | null>(null);

  const sortedImages = useMemo(
    () => [...images].sort((a, b) => a.order - b.order || a.id - b.id),
    [images],
  );
  const sortedSpecs = useMemo(
    () => [...specs].sort((a, b) => a.order - b.order || a.id - b.id),
    [specs],
  );
  const mainImage = useMemo(
    () =>
      sortedImages.find((image) => image.is_main) ?? sortedImages[0] ?? null,
    [sortedImages],
  );

  useEffect(() => {
    if (!slug) {
      setError("Producto no encontrado.");
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        setError(null);
        const [product, categoriesData, brandsData, suppliersData, technicalSheetsData] =
          await Promise.all([
            getAdminProduct(slug),
            getAdminCategories(),
            getAdminBrands(),
            getAdminSuppliers(),
            getTechnicalSheets(),
          ]);

        const [imagesData, specsData] = await Promise.all([
          getProductImages(product.id),
          getProductSpecs(product.id),
        ]);

        const mappedValues = mapProductToFormValues(product);
        setInitialValues(mappedValues);
        setFormValues(mappedValues);
        setProductId(product.id);
        setCategories(categoriesData);
        setBrands(brandsData);
        setSuppliers(suppliersData);
        setTechnicalSheets(technicalSheetsData);
        setImages(imagesData);
        setSpecs(specsData);
      } catch {
        setError("No fue posible cargar el producto para edición.");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [slug]);

  const refreshMediaData = async (nextProductId: number) => {
    const [imagesData, specsData] = await Promise.all([
      getProductImages(nextProductId),
      getProductSpecs(nextProductId),
    ]);
    setImages(imagesData);
    setSpecs(specsData);
  };

  const refreshImages = async (nextProductId: number) => {
    const imagesData = await getProductImages(nextProductId);
    setImages(imagesData);
  };

  const handleSubmit = async (values: ProductFormValues) => {
    if (!slug) return;

    try {
      setIsSubmitting(true);
      setError(null);
      await updateProduct(slug, values);
    } catch {
      setError("No se pudo actualizar el producto.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateImages = async () => {
    if (!productId || imageSaving || pending.images.length === 0) return;
    const queue = pending.images.filter((image) => image.status === "pending" || image.status === "error");
    const successfulIds = new Set<string>();
    let uploaded = 0;
    setImageSaving(true);
    setImageError(null);
    setImageStatus(null);
    for (let index = 0; index < queue.length; index += 1) {
      const image = queue[index];
      pending.updateImage(image.id, { status: "uploading", error: null });
      setImageStatus(`Subiendo ${index + 1} de ${queue.length} imágenes…`);
      try {
        await createProductImage({
          product: productId,
          image: image.file,
          alt_text: image.altText.trim() || previewValues?.name?.trim() || "",
          is_main: image.id === selectedPendingId,
        });
        successfulIds.add(image.id);
        uploaded += 1;
      } catch (uploadError) {
        pending.updateImage(image.id, { status: "error", error: getSafeApiErrorMessage(uploadError, image.id === selectedPendingId ? "No se pudo cargar esta imagen ni actualizar la imagen principal." : "No se pudo cargar esta imagen.") });
      }
    }

    pending.removeSuccessfulImages(successfulIds);
    if (successfulIds.has(selectedPendingId ?? "")) setSelectedPendingId(null);
    try {
      await refreshImages(productId);
      if (uploaded === queue.length) setImageStatus(queue.length === 1 ? "La imagen se cargó correctamente." : "Todas las imágenes se cargaron.");
      else if (uploaded === 0) setImageError("Ninguna imagen pudo cargarse. Revisa cada resultado y vuelve a intentarlo.");
      else setImageError(`Algunas imágenes no pudieron cargarse. Se cargaron ${uploaded} de ${queue.length}.`);
    } catch {
      setImageError("Las imágenes se cargaron, pero la galería no pudo actualizarse. Recarga la página para consultarlas sin volver a subirlas.");
    } finally {
      setImageSaving(false);
    }
  };

  const handleSetMainImage = async (imageId: number) => {
    if (!productId) return;
    try {
      setImageSaving(true);
      setImageError(null);
      setImageStatus(null);
      setSelectedPendingId(null);
      await updateProductImage(imageId, { is_main: true });
      await refreshImages(productId);
      setImageStatus("Imagen principal actualizada.");
    } catch {
      setImageError("No se pudo actualizar la imagen principal.");
    } finally {
      setImageSaving(false);
    }
  };

  const handleDeleteImage = async (imageId: number) => {
    if (!productId) return;
    if (!window.confirm("¿Eliminar esta imagen?")) return;

    try {
      setImageSaving(true);
      setImageError(null);
      setImageStatus(null);
      await deleteProductImage(imageId);
      await refreshImages(productId);
      setImageStatus("Imagen eliminada.");
    } catch {
      setImageError("No se pudo eliminar la imagen.");
    } finally {
      setImageSaving(false);
    }
  };

  const handleCreateSpec = async (event: FormEvent) => {
    event.preventDefault();
    if (!productId) return;

    try {
      setSpecSaving(true);
      setSpecError(null);
      setSpecStatus(null);
      await createProductSpec({
        product: productId,
        name: specForm.name,
        value: specForm.value,
        unit: specForm.unit,
        order: specForm.order,
      });
      await refreshMediaData(productId);
      setSpecForm(initialSpecForm);
      setSpecStatus("Especificación agregada.");
    } catch {
      setSpecError("No se pudo crear la especificación.");
    } finally {
      setSpecSaving(false);
    }
  };

  const handleUpdateSpec = async (
    specId: number,
    payload: Partial<ProductSpecWritePayload>,
  ) => {
    if (!productId) return;

    try {
      setSpecSaving(true);
      setSpecError(null);
      setSpecStatus(null);
      await updateProductSpec(specId, payload);
      await refreshMediaData(productId);
      setSpecStatus("Especificación actualizada.");
    } catch {
      setSpecError("No se pudo actualizar la especificación.");
    } finally {
      setSpecSaving(false);
    }
  };

  const handleDeleteSpec = async (specId: number) => {
    if (!productId) return;
    if (!window.confirm("¿Eliminar esta especificación?")) return;

    try {
      setSpecSaving(true);
      setSpecError(null);
      setSpecStatus(null);
      await deleteProductSpec(specId);
      await refreshMediaData(productId);
      setSpecStatus("Especificación eliminada.");
    } catch {
      setSpecError("No se pudo eliminar la especificación.");
    } finally {
      setSpecSaving(false);
    }
  };

  const handleDeleteProduct = async () => {
    if (!slug) return;

    try {
      setIsDeleting(true);
      setDeleteError(null);
      await deleteProduct(slug);
      navigate("/admin/productos?status=deleted");
    } catch (error) {
      setDeleteError(
        getSafeApiErrorMessage(
          error,
          "No se pudo eliminar el producto. Puedes despublicarlo o revisar si tiene relaciones asociadas.",
        ),
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const previewValues = formValues ?? initialValues;
  const selectedPending = pending.images.find((image) => image.id === selectedPendingId) ?? null;

  return (
    <AdminLayout>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}

      {!loading && initialValues ? (
        <ProductEditorLayout
          title="Editar producto"
          onBack={() => navigate("/admin/productos")}
          formId={PRODUCT_EDIT_FORM_ID}
          isSubmitting={isSubmitting}
          form={
            <ProductForm
              formId={PRODUCT_EDIT_FORM_ID}
              onCancel={() => navigate("/admin/productos")}
              initialValues={initialValues}
              categories={categories}
              brands={brands}
              suppliers={suppliers}
              technicalSheets={technicalSheets}
              onSubmit={handleSubmit}
              isSubmitting={isSubmitting}
              error={error}
              onValuesChange={setFormValues}
              beforeActions={
                <ProductImageManager
                  existingImages={sortedImages}
                  pendingImages={pending.images}
                  selectedPendingId={selectedPendingId}
                  disabled={imageSaving}
                  status={imageStatus}
                  error={pending.selectionError || imageError}
                  uploadLabel={imageSaving ? "Subiendo imágenes…" : `Subir ${pending.images.length} ${pending.images.length === 1 ? "imagen" : "imágenes"}`}
                  onAddFiles={pending.addFiles}
                  onAltTextChange={(id, altText) => pending.updateImage(id, { altText })}
                  onSelectPending={setSelectedPendingId}
                  onRemovePending={pending.removeImage}
                  onSelectExisting={handleSetMainImage}
                  onDeleteExisting={handleDeleteImage}
                  onUpload={handleCreateImages}
                />
              }
            />
          }
          sidebar={
            <div className="admin-product-editor-sidebar">
              <section className="admin-block admin-block--compact admin-product-preview">
                <h2>Vista previa pública</h2>
                <article className="product-card admin-product-preview-card">
                  <div className="product-card__image-area">
                    <img
                      src={selectedPending?.previewUrl || resolveMediaUrl(mainImage?.image) || PLACEHOLDER_IMAGE}
                      alt={selectedPending?.altText.trim() || mainImage?.alt_text || previewValues?.name || "Producto"}
                    />
                  </div>
                  <div className="product-card__content">
                    <div className="product-card__badges">
                      <span className="badge badge--condition">
                        {formatCondition(
                          previewValues?.condition ?? initialValues.condition,
                        )}
                      </span>
                      <span className="badge badge--stock">
                        {formatStockStatus(
                          previewValues?.stock_status ??
                            initialValues.stock_status,
                        )}
                      </span>
                    </div>
                    <h3>{previewValues?.name || "Producto sin nombre"}</h3>
                    {previewValues?.model.trim() ? <p className="product-card__model">{previewValues.model.trim()}</p> : null}
                    <ProductTechnicalData
                      productType={previewValues?.product_type ?? initialValues.product_type}
                      condition={previewValues?.condition ?? initialValues.condition}
                      workingHeightM={previewValues?.working_height_m}
                      maximumLoadCapacityKg={previewValues?.maximum_load_capacity_kg}
                      powerSource={previewValues?.power_source}
                      terrainType={previewValues?.terrain_type}
                    />
                    <p className="product-card__price">
                      {formatPriceValue(
                        previewValues?.price ?? initialValues.price,
                        previewValues?.price_visible ??
                          initialValues.price_visible,
                        previewValues?.price_currency ??
                          initialValues.price_currency,
                        previewValues?.price_tax_mode ??
                          initialValues.price_tax_mode,
                      )}
                    </p>
                  </div>
                  <div className="product-card__actions">
                    <button type="button" className="btn btn--accent" disabled>
                      Ver detalle
                    </button>
                  </div>
                </article>
              </section>
              <section className="admin-block admin-block--compact admin-danger-zone admin-product-delete-panel">
                <h2>Eliminar producto</h2>
                <p className="ui-note">
                  Esta acción es irreversible y solo puede realizarse si el producto no tiene cotizaciones asociadas.
                </p>
                {deleteError ? <p className="ui-note ui-note--error">{deleteError}</p> : null}
                {!deleteConfirmOpen ? (
                  <button type="button" className="btn btn--ghost btn--danger" onClick={() => setDeleteConfirmOpen(true)} disabled={isDeleting}>
                    Eliminar producto
                  </button>
                ) : (
                  <div className="admin-delete-confirmation" role="alert">
                    <p>¿Seguro que deseas eliminar este producto? Esta acción no se puede deshacer.</p>
                    <div className="admin-media-item__actions">
                      <button type="button" className="btn btn--ghost btn--danger" onClick={handleDeleteProduct} disabled={isDeleting}>
                        {isDeleting ? "Eliminando..." : "Sí, eliminar"}
                      </button>
                      <button type="button" className="btn btn--ghost" onClick={() => { setDeleteConfirmOpen(false); setDeleteError(null); }} disabled={isDeleting}>
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
              </section>
            </div>
          }
        />
      ) : null}

      {false && !loading && productId ? (
        <section className="admin-block admin-block--compact">
          <h2>Especificaciones técnicas</h2>
          {specError ? (
            <p className="ui-note ui-note--error">{specError}</p>
          ) : null}
          {specStatus ? (
            <p className="ui-note ui-note--success">{specStatus}</p>
          ) : null}

          <form
            className="admin-inline-form admin-inline-form--compact"
            onSubmit={handleCreateSpec}
          >
            <label>
              Nombre
              <input
                value={specForm.name}
                onChange={(e) =>
                  setSpecForm((prev) => ({ ...prev, name: e.target.value }))
                }
                required
              />
            </label>
            <label>
              Valor
              <input
                value={specForm.value}
                onChange={(e) =>
                  setSpecForm((prev) => ({ ...prev, value: e.target.value }))
                }
                required
              />
            </label>
            <label>
              Unidad
              <input
                value={specForm.unit}
                onChange={(e) =>
                  setSpecForm((prev) => ({ ...prev, unit: e.target.value }))
                }
              />
            </label>
            <label>
              Orden
              <input
                type="number"
                value={specForm.order}
                onChange={(e) =>
                  setSpecForm((prev) => ({
                    ...prev,
                    order: Number(e.target.value) || 0,
                  }))
                }
                min={0}
              />
            </label>
            <button
              type="submit"
              className="btn btn--accent"
              disabled={specSaving}
            >
              {specSaving ? "Guardando..." : "Agregar spec"}
            </button>
          </form>

          {sortedSpecs.length === 0 ? (
            <p className="ui-note">
              Este producto no tiene especificaciones aún.
            </p>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Valor</th>
                    <th>Unidad</th>
                    <th>Orden</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSpecs.map((spec) => (
                    <tr key={spec.id}>
                      <td>
                        <input
                          value={spec.name}
                          onChange={(e) =>
                            setSpecs((prev) =>
                              prev.map((item) =>
                                item.id === spec.id
                                  ? { ...item, name: e.target.value }
                                  : item,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          value={spec.value}
                          onChange={(e) =>
                            setSpecs((prev) =>
                              prev.map((item) =>
                                item.id === spec.id
                                  ? { ...item, value: e.target.value }
                                  : item,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          value={spec.unit}
                          onChange={(e) =>
                            setSpecs((prev) =>
                              prev.map((item) =>
                                item.id === spec.id
                                  ? { ...item, unit: e.target.value }
                                  : item,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={spec.order}
                          onChange={(e) =>
                            setSpecs((prev) =>
                              prev.map((item) =>
                                item.id === spec.id
                                  ? {
                                      ...item,
                                      order: Number(e.target.value) || 0,
                                    }
                                  : item,
                              ),
                            )
                          }
                          min={0}
                        />
                      </td>
                      <td>
                        <div className="admin-media-item__actions">
                          <button
                            type="button"
                            className="btn btn--ghost"
                            onClick={() =>
                              handleUpdateSpec(spec.id, {
                                name: spec.name,
                                value: spec.value,
                                unit: spec.unit,
                                order: spec.order,
                              })
                            }
                            disabled={specSaving}
                          >
                            Guardar
                          </button>
                          <button
                            type="button"
                            className="btn btn--ghost"
                            onClick={() => handleDeleteSpec(spec.id)}
                            disabled={specSaving}
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      {!loading && !initialValues && error ? (
        <p className="ui-note ui-note--error">{error}</p>
      ) : null}
    </AdminLayout>
  );
}
