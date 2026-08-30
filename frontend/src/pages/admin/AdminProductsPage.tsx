import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AdminLayout } from "../../components/admin/AdminLayout";
import { AdminIcon } from "../../components/admin/AdminIcon";
import { AdminPageHeader } from "../../components/admin/AdminPageHeader";
import { AdminProductImage } from "../../components/admin/AdminProductImage";
import { getSafeApiErrorMessage } from "../../services/api";
import { getAdminCategories, getAdminProducts } from "../../services/adminApi";
import type {
  Category,
  ProductCondition,
  ProductListItem,
  StockStatus,
} from "../../types/catalog";
import { formatCondition, formatStockStatus, getRootCategory } from "../../utils/formatters";

const PRODUCT_FILTERS_STORAGE_KEY = "admin-products-filters";
const CONDITION_ORDER: ProductCondition[] = ["new", "used", "refurbished"];
const STOCK_ORDER: StockStatus[] = ["available", "on_request", "reserved", "sold"];

type ProductFiltersState = {
  search: string;
  rootCategoryFilter: string;
  subcategoryFilter: string;
  brandFilter: string;
  conditionFilter: string;
  stockFilter: string;
  publishedFilter: string;
};

type FilterLevel = "root" | "subcategory" | "brand" | "condition" | "stock";
type FilterSelection = Omit<ProductFiltersState, "search" | "publishedFilter">;

type ExplorerNode = {
  id: string;
  label: string;
  level: FilterLevel;
  count: number;
  selection: FilterSelection;
  sortOrder: number;
  children: ExplorerNode[];
};

const emptySelection: FilterSelection = {
  rootCategoryFilter: "",
  subcategoryFilter: "",
  brandFilter: "",
  conditionFilter: "",
  stockFilter: "",
};

const defaultFilters: ProductFiltersState = {
  search: "",
  ...emptySelection,
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
    const conditions = new Set<ProductCondition>(["new", "used", "refurbished"]);
    const stocks = new Set<StockStatus>(["available", "on_request", "reserved", "sold"]);
    return {
      search: parsed.search ?? "",
      rootCategoryFilter: parsed.rootCategoryFilter ?? parsed.typeFilter ?? "",
      subcategoryFilter: parsed.subcategoryFilter ?? parsed.categoryFilter ?? "",
      brandFilter: parsed.brandFilter ?? "",
      conditionFilter: conditions.has(parsed.conditionFilter as ProductCondition)
        ? parsed.conditionFilter ?? ""
        : "",
      stockFilter: stocks.has(parsed.stockFilter as StockStatus)
        ? parsed.stockFilter ?? ""
        : "",
      publishedFilter: ["published", "unpublished", ""].includes(parsed.publishedFilter ?? "")
        ? parsed.publishedFilter ?? ""
        : defaultFilters.publishedFilter,
    };
  } catch {
    return defaultFilters;
  }
}

function selectionMatches(product: ProductListItem, selection: FilterSelection, categories: Category[]) {
  const category = categories.find((item) => item.id === product.category.id) ?? product.category;
  const root = getRootCategory(category, categories) ?? category;
  return (
    (!selection.rootCategoryFilter || root.id.toString() === selection.rootCategoryFilter) &&
    (!selection.subcategoryFilter || category.id.toString() === selection.subcategoryFilter) &&
    (!selection.brandFilter || product.brand?.name === selection.brandFilter) &&
    (!selection.conditionFilter || product.condition === selection.conditionFilter) &&
    (!selection.stockFilter || product.stock_status === selection.stockFilter)
  );
}

function buildExplorerTree(products: ProductListItem[], categories: Category[]) {
  const roots: ExplorerNode[] = [];
  const categoryById = new Map(categories.map((category) => [category.id, category]));

  const addNode = (
    siblings: ExplorerNode[],
    level: FilterLevel,
    value: string,
    label: string,
    selection: FilterSelection,
    sortOrder: number,
  ) => {
    const id = `${level}:${value}:${Object.values(selection).join("|")}`;
    let node = siblings.find((candidate) => candidate.id === id);
    if (!node) {
      node = { id, label, level, count: 0, selection: { ...selection }, sortOrder, children: [] };
      siblings.push(node);
    }
    node.count += 1;
    return node;
  };

  products.forEach((product) => {
    const category = categoryById.get(product.category.id) ?? product.category;
    const root = getRootCategory(category, categories) ?? category;
    let selection = { ...emptySelection, rootCategoryFilter: root.id.toString() };
    let node = addNode(roots, "root", root.id.toString(), root.name, selection, root.order ?? 0);

    if (category.parent && category.id !== root.id) {
      selection = { ...selection, subcategoryFilter: category.id.toString() };
      node = addNode(node.children, "subcategory", category.id.toString(), category.name, selection, category.order ?? 0);
    }
    if (product.brand?.name) {
      selection = { ...selection, brandFilter: product.brand.name };
      node = addNode(node.children, "brand", product.brand.name, product.brand.name, selection, 0);
    }
    if (product.condition !== "not_applicable") {
      selection = { ...selection, conditionFilter: product.condition };
      node = addNode(
        node.children,
        "condition",
        product.condition,
        formatCondition(product.condition),
        selection,
        CONDITION_ORDER.indexOf(product.condition),
      );
    }
    selection = { ...selection, stockFilter: product.stock_status };
    addNode(
      node.children,
      "stock",
      product.stock_status,
      formatStockStatus(product.stock_status),
      selection,
      STOCK_ORDER.indexOf(product.stock_status),
    );
  });

  const sortNodes = (nodes: ExplorerNode[]) => {
    nodes.sort((a, b) => a.sortOrder - b.sortOrder || a.label.localeCompare(b.label, "es"));
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(roots);
  return roots;
}

function sameSelection(left: FilterSelection, right: FilterSelection) {
  return Object.keys(emptySelection).every(
    (key) => left[key as keyof FilterSelection] === right[key as keyof FilterSelection],
  );
}

export function AdminProductsPage() {
  const [searchParams] = useSearchParams();
  const storedFilters = useMemo(() => readStoredFilters(), []);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [searchInput, setSearchInput] = useState(storedFilters.search);
  const [appliedSearch, setAppliedSearch] = useState(storedFilters.search);
  const [selection, setSelection] = useState<FilterSelection>(storedFilters);
  const [publishedFilter, setPublishedFilter] = useState(storedFilters.publishedFilter);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filtersOpen, setFiltersOpen] = useState(false);
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
      JSON.stringify({ search: appliedSearch, ...selection, publishedFilter }),
    );
  }, [appliedSearch, selection, publishedFilter]);

  const tree = useMemo(() => buildExplorerTree(products, categories), [products, categories]);

  useEffect(() => {
    if (!hasLoadedProducts || categories.length === 0) return;
    const levels: (keyof FilterSelection)[] = [
      "rootCategoryFilter", "subcategoryFilter", "brandFilter", "conditionFilter", "stockFilter",
    ];
    let valid = { ...emptySelection };
    for (const level of levels) {
      const value = selection[level];
      if (!value) continue;
      const candidate = { ...valid, [level]: value };
      if (products.some((product) => selectionMatches(product, candidate, categories))) valid = candidate;
      else break;
    }
    if (!sameSelection(valid, selection)) setSelection(valid);
  }, [products, categories, hasLoadedProducts, selection]);

  useEffect(() => {
    const ancestorIds = new Set<string>();
    const visit = (nodes: ExplorerNode[]) => {
      nodes.forEach((node) => {
        const selectedValues = Object.values(selection).filter(Boolean);
        const nodeValues = Object.values(node.selection).filter(Boolean);
        if (nodeValues.every((value) => selectedValues.includes(value))) ancestorIds.add(node.id);
        visit(node.children);
      });
    };
    visit(tree);
    if (ancestorIds.size) setExpanded((current) => new Set([...current, ...ancestorIds]));
  }, [tree, selection]);

  const filteredProducts = useMemo(
    () => products.filter((product) => selectionMatches(product, selection, categories)),
    [products, selection, categories],
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

  const clearFilters = () => {
    setSearchInput(""); setAppliedSearch(""); setSelection(emptySelection);
    setPublishedFilter("published");
    void loadProducts("", "published");
  };

  const showAll = () => {
    setSearchInput(""); setAppliedSearch(""); setSelection(emptySelection);
    setPublishedFilter("");
    void loadProducts("", "");
  };

  const toggleExpanded = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const renderNodes = (nodes: ExplorerNode[]) => (
    <ul className="admin-product-explorer__list">
      {nodes.map((node) => {
        const isSelected = sameSelection(selection, node.selection);
        const isExpanded = expanded.has(node.id);
        return (
          <li key={node.id}>
            <div className={`admin-product-explorer__node${isSelected ? " admin-product-explorer__node--selected" : ""}`}>
              {node.children.length ? (
                <button type="button" className="admin-product-explorer__toggle" aria-label={`${isExpanded ? "Contraer" : "Expandir"} ${node.label}`} aria-expanded={isExpanded} onClick={() => toggleExpanded(node.id)}>
                  <span aria-hidden="true">{isExpanded ? "▾" : "▸"}</span>
                </button>
              ) : <span className="admin-product-explorer__toggle-placeholder" aria-hidden="true" />}
              <button type="button" className="admin-product-explorer__select" aria-current={isSelected ? "true" : undefined} onClick={() => setSelection(node.selection)}>
                <span>{node.label}</span><span className="admin-product-explorer__count">({node.count})</span>
              </button>
            </div>
            {node.children.length && isExpanded ? renderNodes(node.children) : null}
          </li>
        );
      })}
    </ul>
  );

  return (
    <AdminLayout>
      <div className="admin-products-list">
        <AdminPageHeader title="Productos" actions={<Link className="btn btn--accent" to="/admin/productos/nuevo"><AdminIcon name="plus" />Nuevo producto</Link>} />
        <div className="admin-products-list__messages" aria-live="polite">
          {loading ? <p className="ui-note">Cargando productos...</p> : null}
          {error ? <p className="ui-note ui-note--error" role="alert">{error}</p> : null}
          {success ? <p className="ui-note ui-note--success">{success}</p> : null}
        </div>
        <button type="button" className="btn btn--ghost admin-products-filter-toggle" aria-expanded={filtersOpen} aria-controls="admin-product-explorer" onClick={() => setFiltersOpen((open) => !open)}>
          {filtersOpen ? "Ocultar filtros" : "Mostrar filtros"}
        </button>
        <div className="admin-products-workspace">
          <aside id="admin-product-explorer" className={`admin-product-explorer${filtersOpen ? " admin-product-explorer--open" : ""}`} aria-label="Filtros de productos">
            <form className="admin-product-explorer__controls" onSubmit={(event) => { event.preventDefault(); applySearch(); }}>
              <label className="admin-products-filter-field"><span>Buscar productos</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Nombre, marca, categoría o SKU" /></label>
              <label className="admin-products-filter-field"><span>Publicación</span><select value={publishedFilter} onChange={(event) => changePublication(event.target.value)}><option value="published">Solo publicados</option><option value="unpublished">Solo no publicados</option><option value="">Todos</option></select></label>
              <div className="admin-products-filter-actions"><button type="submit" className="btn btn--accent"><AdminIcon name="search" />Buscar</button><button type="button" className="btn btn--ghost" onClick={clearFilters}><AdminIcon name="reset" />Limpiar filtros</button><button type="button" className="btn btn--ghost" onClick={showAll}>Ver todo</button></div>
            </form>
            <nav className="admin-product-explorer__tree" aria-label="Jerarquía de productos">
              <button type="button" className={`admin-product-explorer__all${sameSelection(selection, emptySelection) ? " admin-product-explorer__all--selected" : ""}`} aria-current={sameSelection(selection, emptySelection) ? "true" : undefined} onClick={() => setSelection(emptySelection)}><span>Todos los productos</span><span>({products.length})</span></button>
              {tree.length ? renderNodes(tree) : <p className="admin-product-explorer__empty">Sin ramas para los criterios aplicados.</p>}
            </nav>
          </aside>
          <section className="admin-products-results" aria-label="Resultados de productos">
            {!loading && !error && filteredProducts.length === 0 ? <p className="ui-note">{!hasLoadedProducts || (products.length === 0 && !appliedSearch && publishedFilter === "") ? "No existen productos" : "No hay productos para los criterios seleccionados"}</p> : null}
            {!loading && !error && filteredProducts.length > 0 ? (
              <div className="admin-table-wrapper admin-products-table-wrapper" tabIndex={0} aria-label="Tabla de productos con desplazamiento horizontal">
                <table className="admin-table admin-products-table"><thead><tr><th scope="col">Nombre</th><th scope="col">Categoría / Subcategoría</th><th scope="col">Marca</th><th scope="col">Condición</th><th scope="col">Disponibilidad</th><th scope="col">Estado</th><th scope="col">Actualizado</th><th scope="col">Acciones</th></tr></thead>
                  <tbody>{filteredProducts.map((product) => {
                    const category = categories.find((item) => item.id === product.category.id) ?? product.category;
                    const root = getRootCategory(category, categories) ?? category;
                    const subcategory = category.parent && category.id !== root.id ? category.name : "—";
                    return <tr key={product.id}><td><div className="admin-products-table__name"><div className="admin-products-table__thumbnail">{product.main_image ? <AdminProductImage imageId={product.main_image.id} alt={product.main_image.alt_text.trim() || product.name} /> : <div className="admin-products-table__placeholder" role="img" aria-label={`Sin imagen para ${product.name}`} />}</div><span className="admin-products-table__name-text">{product.name}</span></div></td><td><span>{root.name}</span><span className="admin-products-table__secondary">{subcategory}</span></td><td>{product.brand?.name ?? "—"}</td><td>{formatCondition(product.condition)}</td><td><span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span></td><td><div className="admin-products-table__status"><span className={`badge ${product.is_featured ? "badge--ok" : "badge--muted"}`}>{product.is_featured ? "Destacado" : "Normal"}</span><span className={`badge ${product.is_published ? "badge--ok" : "badge--muted"}`}>{product.is_published ? "Publicado" : "No publicado"}</span></div></td><td>{product.updated_at ? new Date(product.updated_at).toLocaleDateString("es-CL") : "—"}</td><td><Link className="table-action" to={`/admin/productos/${product.slug}/editar`}><AdminIcon name="edit" />Editar</Link></td></tr>;
                  })}</tbody>
                </table>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </AdminLayout>
  );
}
