using System.Collections.Immutable;

namespace JemNexus.Api.Models;

public static class AppPermissions
{
    public const int MaxLength = 80;
    public const string ProductsCreate = "products.create";
    public const string ProductsUpdate = "products.update";
    public const string ProductsDelete = "products.delete";
    public const string ProductImagesManage = "product_images.manage";
    public const string ProductSpecsManage = "product_specs.manage";
    public const string TechnicalSheetsCreate = "technical_sheets.create";
    public const string TechnicalSheetsUpdate = "technical_sheets.update";
    public const string TechnicalSheetsDelete = "technical_sheets.delete";
    public const string CategoriesCreate = "categories.create";
    public const string CategoriesUpdate = "categories.update";
    public const string CategoriesDelete = "categories.delete";
    public const string BrandsCreate = "brands.create";
    public const string BrandsUpdate = "brands.update";
    public const string BrandsDelete = "brands.delete";
    public const string SuppliersCreate = "suppliers.create";
    public const string SuppliersUpdate = "suppliers.update";
    public const string SuppliersDelete = "suppliers.delete";
    public const string CustomersCreate = "customers.create";
    public const string CustomersUpdate = "customers.update";
    public const string CustomersSetStatus = "customers.set_status";
    public const string QuoteRequestsUpdate = "quote_requests.update";
    public const string CommercialQuotesIssue = "commercial_quotes.issue";
    public const string QuoteNotificationsTest = "quote_notifications.test";
    public const string PromotionsCreate = "promotions.create";
    public const string PromotionsUpdate = "promotions.update";
    public const string PromotionsDelete = "promotions.delete";
    public const string HomeSectionsCreate = "home_sections.create";
    public const string HomeSectionsUpdate = "home_sections.update";
    public const string HomeSectionsDelete = "home_sections.delete";
    public const string UsersManage = "users.manage";

    public static ImmutableArray<string> SellerGrantable { get; } =
    [
        BrandsCreate, BrandsDelete, BrandsUpdate, CategoriesCreate, CategoriesDelete, CategoriesUpdate,
        CommercialQuotesIssue, CustomersCreate, CustomersSetStatus, CustomersUpdate,
        HomeSectionsCreate, HomeSectionsDelete, HomeSectionsUpdate, ProductImagesManage, ProductSpecsManage,
        ProductsCreate, ProductsDelete, ProductsUpdate, PromotionsCreate, PromotionsDelete, PromotionsUpdate,
        QuoteNotificationsTest, QuoteRequestsUpdate, SuppliersCreate, SuppliersDelete, SuppliersUpdate,
        TechnicalSheetsCreate, TechnicalSheetsDelete, TechnicalSheetsUpdate
    ];

    public static ImmutableArray<string> Reserved { get; } = [UsersManage];
    public static ImmutableArray<string> All { get; } = [.. SellerGrantable, .. Reserved];

    public static bool IsKnown(string? permission) => permission is not null && All.Contains(permission, StringComparer.Ordinal);
    public static bool IsSellerGrantable(string? permission) => permission is not null && SellerGrantable.Contains(permission, StringComparer.Ordinal);
}
