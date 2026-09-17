import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AdminLayout } from "../../components/admin/AdminLayout";
import { AdminIcon } from "../../components/admin/AdminIcon";
import { AdminPageHeader } from "../../components/admin/AdminPageHeader";
import { AdminProductImage } from "../../components/admin/AdminProductImage";
import { getSafeApiErrorMessage } from "../../services/api";
import { getAdminCategories, getAdminProducts } from "../../services/adminApi";
import type { Category, ProductListItem } from "../../types/catalog";
import { formatCondition, formatStockStatus, getRootCategory } from "../../utils/formatters";

const PRODUCT_FILTERS_STORAGE_KEY = "admin-products-filters";

type ProductFiltersState = {
  search: string;
  rootCategoryFilter: string;
  subcategoryFilter: string;
  publishedFilter: string;
};

const defaultFilters: ProductFiltersState = {
  search: "",
  rootCategoryFilter: "",
  subcategoryFilter: "",
  publishedFilter: "published",
};

function readStoredFilters(): ProductFiltersState {
  if (typeof window === "undefined") return defaultFilters;
  const rawFilters = window.sessionStorage.getItem(PRODUCT_FILTERS_STORAGE_KEY);
  if (!rawFilters) return defaultFilters;

  try {
    const parsed = JSON.parse(rawFilters) as Partial<ProductFiltersState> & {
      typeFilter?: string;
      categoryFilter?: string;
    };
    return {
      search: typeof parsed.search === "string" ? parsed.search : "",
      rootCategoryFilter:
        typeof parsed.rootCategoryFilter === "string"
          ? parsed.rootCategoryFilter
          : typeof parsed.typeFilter === "string"
            ? parsed.typeFilter
            : "",
      subcategoryFilter:
        typeof parsed.subcategoryFilter === "string"
          ? parsed.subcategoryFilter
          : typeof parsed.categoryFilter === "string"
            ? parsed.categoryFilter
            : "",
      publishedFilter: ["published", "unpublished", ""].includes(parsed.publishedFilter ?? "")
        ? parsed.publishedFilter ?? ""
        : defaultFilters.publishedFilter,
    };
  } catch {
    return defaultFilters;
  }
}

function sortCategories(left: Category, right: Category) {
  return left.order - right.order || left.name.localeCompare(right.name, "es");
}

export function AdminProductsPage() {
  const [searchParams] = useSearchParams();
  const storedFilters = useMemo(() => readStoredFilters(), []);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [searchInput, setSearchInput] = useState(storedFilters.search);
  const [appliedSearch, setAppliedSearch] = useState(storedFilters.search);
  const [rootCategoryFilter, setRootCategoryFilter] = useState(storedFilters.rootCategoryFilter);
  const [subcategoryFilter, setSubcategoryFilter] = useState(storedFilters.subcategoryFilter);
  const [publishedFilter, setPublishedFilter] = useState(storedFilters.publishedFilter);
  const [loading, setLoading] = useState(false);
  const [hasLoadedProducts, setHasLoadedProducts] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const [success] = useState<string | null>(
    searchParams.get("status") === "created"
      ? "Producto creado correctamente."
      : searchParams.get("status") === "updated"
        ? "Producto actualizado correctamente."
        : searchParams.get("status") === "deleted"
          ? "Producto eliminado correctamente."
          : null,
  );

  const loadProducts = async (search: string, publication: string) => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getAdminProducts({
        search: search.trim() || undefined,
        is_published: publication === "published" ? true : publication === "unpublished" ? false : undefined,
      });
      if (currentRequest !== requestId.current) return;
      setProducts(response);
      setHasLoadedProducts(true);
    } catch (caughtError) {
      if (currentRequest !== requestId.current) return;
      setError(getSafeApiErrorMessage(caughtError, "No se pudo cargar el listado de productos."));
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    void getAdminCategories()
      .then((response) => { if (active) setCategories(response); })
      .catch((caughtError) => {
        if (active) setError(getSafeApiErrorMessage(caughtError, "No se pudieron cargar las categorías."));
      });
    void loadProducts(storedFilters.search, storedFilters.publishedFilter);
    return () => {
      active = false;
      requestId.current += 1;
    };
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem(
      PRODUCT_FILTERS_STORAGE_KEY,
      JSON.stringify({ search: appliedSearch, rootCategoryFilter, subcategoryFilter, publishedFilter }),
    );
  }, [appliedSearch, rootCategoryFilter, subcategoryFilter, publishedFilter]);

  const rootCategories = useMemo(
    () => categories.filter((category) => category.parent === null).sort(sortCategories),
    [categories],
  );

  const subcategories = useMemo(() => {
    if (!rootCategoryFilter) return [];
    return categories
      .filter((category) => {
        const root = getRootCategory(category, categories);
        return category.parent !== null && root?.id.toString() === rootCategoryFilter;
      })
      .sort(sortCategories);
  }, [categories, rootCategoryFilter]);

  useEffect(() => {
    if (categories.length === 0) return;
    const validRoot = rootCategories.some((category) => category.id.toString() === rootCategoryFilter);
    if (rootCategoryFilter && !validRoot) {
      setRootCategoryFilter("");
      setSubcategoryFilter("");
      return;
    }
    if (!rootCategoryFilter || !subcategories.some((category) => category.id.toString() === subcategoryFilter)) {
      if (subcategoryFilter) setSubcategoryFilter("");
    }
  }, [categories, rootCategories, rootCategoryFilter, subcategories, subcategoryFilter]);

  const filteredProducts = useMemo(
    () => products.filter((product) => {
      if (!rootCategoryFilter) return true;
      const category = categories.find((item) => item.id === product.category.id) ?? product.category;
      const root = getRootCategory(category, categories) ?? category;
      if (root.id.toString() !== rootCategoryFilter) return false;
      return !subcategoryFilter || category.id.toString() === subcategoryFilter;
    }),
    [products, categories, rootCategoryFilter, subcategoryFilter],
  );

  const applySearch = () => {
    const nextSearch = searchInput.trim();
    setAppliedSearch(nextSearch);
    void loadProducts(nextSearch, publishedFilter);
  };

  const changePublication = (value: string) => {
    setPublishedFilter(value);
    void loadProducts(appliedSearch, value);
  };

  const changeRootCategory = (value: string) => {
    setRootCategoryFilter(value);
    setSubcategoryFilter("");
  };

  const clearFilters = () => {
    setSearchInput("");
    setAppliedSearch("");
    setRootCategoryFilter("");
    setSubcategoryFilter("");
    setPublishedFilter("published");
    void loadProducts("", "published");
  };

  const showAll = () => {
    setSearchInput("");
    setAppliedSearch("");
    setRootCategoryFilter("");
    setSubcategoryFilter("");
    setPublishedFilter("");
    void loadProducts("", "");
  };

  return (
    <AdminLayout>
      <div className="admin-products-list">
        <AdminPageHeader title="Productos" actions={<Link className="btn btn--accent" to="/admin/productos/nuevo"><AdminIcon name="plus" />Nuevo producto</Link>} />
        <div className="admin-products-list__messages" aria-live="polite">
          {loading ? <p className="ui-note">Cargando productos...</p> : null}
          {error ? <p className="ui-note ui-note--error" role="alert">{error}</p> : null}
          {success ? <p className="ui-note ui-note--success">{success}</p> : null}
        </div>
        <form className="admin-products-filters" aria-label="Filtros de productos" onSubmit={(event) => { event.preventDefault(); applySearch(); }}>
          <label className="admin-products-filter-field admin-products-filter-field--search"><span>Buscar productos</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Nombre, marca, categoría o SKU" /></label>
          <label className="admin-products-filter-field"><span>Publicación</span><select value={publishedFilter} onChange={(event) => changePublication(event.target.value)}><option value="published">Solo publicados</option><option value="unpublished">Solo no publicados</option><option value="">Todos</option></select></label>
          <label className="admin-products-filter-field"><span>Categoría</span><select value={rootCategoryFilter} onChange={(event) => changeRootCategory(event.target.value)}><option value="">Todas las categorías</option>{rootCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label className="admin-products-filter-field"><span>Subcategoría</span><select value={subcategoryFilter} disabled={!rootCategoryFilter} onChange={(event) => setSubcategoryFilter(event.target.value)}><option value="">Todas las subcategorías</option>{subcategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <div className="admin-products-filter-actions"><button type="submit" className="btn btn--accent"><AdminIcon name="search" />Buscar</button><button type="button" className="btn btn--ghost" onClick={clearFilters}><AdminIcon name="reset" />Limpiar filtros</button><button type="button" className="btn btn--ghost" onClick={showAll}>Ver todo</button></div>
        </form>
        <section className="admin-products-results" aria-label="Resultados de productos">
          {!loading && !error && filteredProducts.length === 0 ? <p className="ui-note">{!hasLoadedProducts || (products.length === 0 && !appliedSearch && publishedFilter === "") ? "No existen productos" : "No hay productos para los criterios seleccionados"}</p> : null}
          {!loading && !error && filteredProducts.length > 0 ? (
            <div className="admin-table-wrapper admin-products-table-wrapper" tabIndex={0} aria-label="Tabla de productos con desplazamiento horizontal">
              <table className="admin-table admin-products-table"><thead><tr><th scope="col">Nombre</th><th scope="col">Categoría / Subcategoría</th><th scope="col">Marca</th><th scope="col">Condición</th><th scope="col">Disponibilidad</th><th scope="col">Estado</th><th scope="col">Actualizado</th><th scope="col">Acciones</th></tr></thead>
                <tbody>{filteredProducts.map((product) => {
                  const category = categories.find((item) => item.id === product.category.id) ?? product.category;
                  const root = getRootCategory(category, categories) ?? category;
                  const subcategory = category.parent && category.id !== root.id ? category.name : "—";
                  return <tr key={product.id}><td><div className="admin-products-table__name"><div className="admin-products-table__thumbnail">{product.main_image ? <AdminProductImage imageId={product.main_image.id} alt={product.main_image.alt_text.trim() || product.name} normalizeWhitespace /> : <div className="admin-products-table__placeholder" role="img" aria-label={`Sin imagen para ${product.name}`} />}</div><span className="admin-products-table__name-text">{product.name}</span></div></td><td><span>{root.name}</span><span className="admin-products-table__secondary">{subcategory}</span></td><td>{product.brand?.name ?? "—"}</td><td>{formatCondition(product.condition)}</td><td><span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span></td><td><div className="admin-products-table__status"><span className={`badge ${product.is_featured ? "badge--ok" : "badge--muted"}`}>{product.is_featured ? "Destacado" : "Normal"}</span><span className={`badge ${product.is_published ? "badge--ok" : "badge--muted"}`}>{product.is_published ? "Publicado" : "No publicado"}</span></div></td><td>{product.updated_at ? new Date(product.updated_at).toLocaleDateString("es-CL") : "—"}</td><td><Link className="table-action" to={`/admin/productos/${product.slug}/editar`}><AdminIcon name="edit" />Editar</Link></td></tr>;
                })}</tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </AdminLayout>
  );
}
