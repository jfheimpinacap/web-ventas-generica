import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AdminLayout } from "../../components/admin/AdminLayout";
import { getSafeApiErrorMessage } from "../../services/api";
import { getAdminCategories, getAdminProducts } from "../../services/adminApi";
import type { Category, ProductListItem } from "../../types/catalog";
import { getRootCategory } from "../../utils/formatters";

const PRODUCT_FILTERS_STORAGE_KEY = "admin-products-filters";

type ProductFiltersState = {
  search: string;
  rootCategoryFilter: string;
  subcategoryFilter: string;
  brandFilter: string;
  conditionFilter: string;
  stockFilter: string;
  publishedFilter: string;
};

const defaultFilters: ProductFiltersState = {
  search: "",
  rootCategoryFilter: "",
  subcategoryFilter: "",
  brandFilter: "",
  conditionFilter: "",
  stockFilter: "",
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
      search: parsed.search ?? "",
      rootCategoryFilter: parsed.rootCategoryFilter ?? parsed.typeFilter ?? "",
      subcategoryFilter:
        parsed.subcategoryFilter ?? parsed.categoryFilter ?? "",
      brandFilter: parsed.brandFilter ?? "",
      conditionFilter: parsed.conditionFilter ?? "",
      stockFilter: parsed.stockFilter ?? "",
      publishedFilter: parsed.publishedFilter ?? defaultFilters.publishedFilter,
    };
  } catch {
    return defaultFilters;
  }
}

function stockLabel(stock: ProductListItem["stock_status"]) {
  if (stock === "available") return "Disponible";
  if (stock === "on_request") return "A pedido";
  if (stock === "reserved") return "Reservado";
  return "Vendido";
}

export function AdminProductsPage() {
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const storedFilters = useMemo(() => readStoredFilters(), []);
  const [search, setSearch] = useState(storedFilters.search);
  const [rootCategoryFilter, setRootCategoryFilter] = useState(
    storedFilters.rootCategoryFilter,
  );
  const [subcategoryFilter, setSubcategoryFilter] = useState(
    storedFilters.subcategoryFilter,
  );
  const [brandFilter, setBrandFilter] = useState(storedFilters.brandFilter);
  const [conditionFilter, setConditionFilter] = useState(
    storedFilters.conditionFilter,
  );
  const [stockFilter, setStockFilter] = useState(storedFilters.stockFilter);
  const [publishedFilter, setPublishedFilter] = useState(
    storedFilters.publishedFilter,
  );
  const [loading, setLoading] = useState(false);
  const [hasLoadedProducts, setHasLoadedProducts] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(
    searchParams.get("status") === "created"
      ? "Producto creado correctamente."
      : searchParams.get("status") === "updated"
        ? "Producto actualizado correctamente."
        : searchParams.get("status") === "deleted"
          ? "Producto eliminado correctamente."
          : null,
  );

  const loadProducts = async (
    overrideFilters?: Partial<ProductFiltersState>,
  ) => {
    try {
      setLoading(true);
      setError(null);
      const activeFilters = {
        search,
        rootCategoryFilter,
        subcategoryFilter,
        brandFilter,
        conditionFilter,
        stockFilter,
        publishedFilter,
        ...(overrideFilters ?? {}),
      };
      const selectedCategory =
        activeFilters.subcategoryFilter || activeFilters.rootCategoryFilter;
      const response = await getAdminProducts({
        search: activeFilters.search.trim() || undefined,
        category: selectedCategory || undefined,
        brand: activeFilters.brandFilter || undefined,
        condition: activeFilters.conditionFilter || undefined,
        stock_status: activeFilters.stockFilter || undefined,
        is_published:
          activeFilters.publishedFilter === "published"
            ? true
            : activeFilters.publishedFilter === "unpublished"
              ? false
              : undefined,
      });
      setProducts(response);
      setHasLoadedProducts(true);
    } catch (error) {
      setError(
        getSafeApiErrorMessage(
          error,
          "No se pudo cargar el listado de productos.",
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const hasCriteria = useMemo(
    () =>
      [
        search,
        rootCategoryFilter,
        subcategoryFilter,
        brandFilter,
        conditionFilter,
        stockFilter,
        publishedFilter,
      ].some((value) => value.trim() !== ""),
    [
      search,
      rootCategoryFilter,
      subcategoryFilter,
      brandFilter,
      conditionFilter,
      stockFilter,
      publishedFilter,
    ],
  );

  useEffect(() => {
    if (hasCriteria && !hasLoadedProducts && !loading) {
      void loadProducts();
    }
  }, [hasCriteria, hasLoadedProducts, loading]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const filtersToStore: ProductFiltersState = {
      search,
      rootCategoryFilter,
      subcategoryFilter,
      brandFilter,
      conditionFilter,
      stockFilter,
      publishedFilter,
    };

    window.sessionStorage.setItem(
      PRODUCT_FILTERS_STORAGE_KEY,
      JSON.stringify(filtersToStore),
    );
  }, [
    search,
    rootCategoryFilter,
    subcategoryFilter,
    brandFilter,
    conditionFilter,
    stockFilter,
    publishedFilter,
  ]);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const response = await getAdminCategories();
        setCategories(response);
      } catch (error) {
        setError(
          getSafeApiErrorMessage(
            error,
            "No se pudieron cargar las categorías.",
          ),
        );
      }
    };

    void loadCategories();
    void loadProducts();
  }, []);

  useEffect(() => {
    if (!rootCategoryFilter) {
      if (subcategoryFilter) setSubcategoryFilter("");
      return;
    }

    const subcategory = categories.find(
      (item) => item.id.toString() === subcategoryFilter,
    );
    if (subcategory && subcategory.parent?.toString() !== rootCategoryFilter) {
      setSubcategoryFilter("");
    }
  }, [categories, rootCategoryFilter, subcategoryFilter]);

  const rootCategoryOptions = useMemo(
    () =>
      categories.filter(
        (category) => category.parent === null && category.is_active,
      ),
    [categories],
  );
  const subcategoryOptions = useMemo(
    () =>
      rootCategoryFilter
        ? categories.filter(
            (category) =>
              category.parent?.toString() === rootCategoryFilter &&
              category.is_active,
          )
        : [],
    [categories, rootCategoryFilter],
  );
  const brandOptions = useMemo(
    () =>
      Array.from(new Set(products.map((p) => p.brand?.name).filter(Boolean))),
    [products],
  );

  const categoryById = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories],
  );

  const getProductCategoryDisplay = (product: ProductListItem) => {
    const category = categoryById.get(product.category.id) ?? product.category;
    const rootCategory = getRootCategory(category, categories) ?? category;
    const subcategory = category.parent ? category : null;

    return {
      rootName: rootCategory?.name ?? "-",
      subcategoryName: subcategory?.name ?? "—",
    };
  };

  const filteredProducts = products;

  const handleSearch = () => {
    void loadProducts();
  };

  const clearFilters = () => {
    setSearch("");
    setRootCategoryFilter("");
    setSubcategoryFilter("");
    setBrandFilter("");
    setConditionFilter("");
    setStockFilter("");
    setPublishedFilter(defaultFilters.publishedFilter);
    void loadProducts(defaultFilters);
  };

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Productos</h1>
        <div className="admin-list-toolbar">
          <Link className="btn btn--accent" to="/admin/productos/nuevo">
            Nuevo producto
          </Link>
        </div>
      </div>
      <section
        className="admin-products-filter-panel"
        aria-label="Filtros de productos"
      >
        <input
          className="admin-search admin-products-filter-panel__search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nombre, marca, categoría o SKU"
        />
        <div className="admin-filter-strip admin-filter-strip--products">
          <select
            value={rootCategoryFilter}
            onChange={(event) => setRootCategoryFilter(event.target.value)}
          >
            <option value="">Categoría</option>
            {rootCategoryOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
          <select
            value={subcategoryFilter}
            onChange={(event) => setSubcategoryFilter(event.target.value)}
            disabled={!rootCategoryFilter}
          >
            <option value="">
              {rootCategoryFilter
                ? "Subcategoría"
                : "Selecciona una categoría primero"}
            </option>
            {subcategoryOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
          <select
            value={brandFilter}
            onChange={(event) => setBrandFilter(event.target.value)}
          >
            <option value="">Marca</option>
            {brandOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select
            value={conditionFilter}
            onChange={(event) => setConditionFilter(event.target.value)}
          >
            <option value="">Condición</option>
            <option value="new">Nuevo</option>
            <option value="used">Usado</option>
            <option value="refurbished">Reacondicionado</option>
            <option value="not_applicable">No aplica</option>
          </select>
          <select
            value={stockFilter}
            onChange={(event) => setStockFilter(event.target.value)}
          >
            <option value="">Stock</option>
            <option value="available">Disponible</option>
            <option value="on_request">A pedido</option>
            <option value="reserved">Reservado</option>
            <option value="sold">Vendido</option>
          </select>
          <select
            value={publishedFilter}
            onChange={(event) => setPublishedFilter(event.target.value)}
          >
            <option value="published">Solo publicados</option>
            <option value="unpublished">Solo no publicados</option>
            <option value="">Todos</option>
          </select>
          <button
            type="button"
            className="btn btn--accent"
            onClick={handleSearch}
          >
            Buscar
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={clearFilters}
          >
            Limpiar filtros
          </button>
        </div>
      </section>

      {loading ? <p className="ui-note">Cargando productos...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {success ? <p className="ui-note ui-note--success">{success}</p> : null}

      {!loading && !error && filteredProducts.length === 0 ? (
        <p className="ui-note">
          No hay productos para los criterios seleccionados.
        </p>
      ) : null}

      {!loading && !error && filteredProducts.length > 0 ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Categoría</th>
                <th>Marca</th>
                <th>Subcategoría</th>
                <th>Condición</th>
                <th>Stock</th>
                <th>Destacado</th>
                <th>Publicado</th>
                <th>Actualizado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((product) => {
                const categoryDisplay = getProductCategoryDisplay(product);

                return (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  <td>{categoryDisplay.rootName}</td>
                  <td>{product.brand?.name ?? "-"}</td>
                  <td>{categoryDisplay.subcategoryName}</td>
                  <td>{product.condition}</td>
                  <td>
                    <span className="badge badge--stock">
                      {stockLabel(product.stock_status)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${product.is_featured ? "badge--ok" : "badge--muted"}`}
                    >
                      {product.is_featured ? "Sí" : "No"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${product.is_published ? "badge--ok" : "badge--muted"}`}
                    >
                      {product.is_published ? "Sí" : "No"}
                    </span>
                  </td>
                  <td>
                    {product.updated_at
                      ? new Date(product.updated_at).toLocaleDateString()
                      : "-"}
                  </td>
                  <td>
                    <Link
                      className="table-action"
                      to={`/admin/productos/${product.slug}/editar`}
                    >
                      Editar
                    </Link>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  );
}
