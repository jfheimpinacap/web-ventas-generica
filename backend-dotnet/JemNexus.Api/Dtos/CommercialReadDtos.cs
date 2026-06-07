using JemNexus.Api.Models;

namespace JemNexus.Api.Dtos;

public sealed record CategoryReadDto(
    int Id,
    string Name,
    string Slug,
    int? Parent,
    string Description,
    bool IsActive,
    int Order,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static CategoryReadDto FromCategory(Category category) => new(
        category.Id,
        category.Name,
        category.Slug,
        category.ParentId,
        category.Description,
        category.IsActive,
        category.Order,
        category.CreatedAt,
        category.UpdatedAt);
}

public sealed record BrandReadDto(
    int Id,
    string Name,
    string Slug,
    string? Logo,
    string Description,
    bool IsActive,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static BrandReadDto FromBrand(Brand brand) => new(
        brand.Id,
        brand.Name,
        brand.Slug,
        brand.Logo,
        brand.Description,
        brand.IsActive,
        brand.CreatedAt,
        brand.UpdatedAt);
}

public sealed record SupplierReadDto(
    int Id,
    string Name,
    string ContactName,
    string Phone,
    string Email,
    string Notes,
    bool IsActive,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static SupplierReadDto FromSupplier(Supplier supplier) => new(
        supplier.Id,
        supplier.Name,
        supplier.ContactName,
        supplier.Phone,
        supplier.Email,
        supplier.Notes,
        supplier.IsActive,
        supplier.CreatedAt,
        supplier.UpdatedAt);
}

public sealed record ProductImageReadDto(
    int Id,
    int Product,
    string Image,
    string AltText,
    bool IsMain,
    int Order,
    DateTimeOffset CreatedAt)
{
    public static ProductImageReadDto FromImage(ProductImage image) => new(
        image.Id,
        image.ProductId,
        image.Image,
        image.AltText,
        image.IsMain,
        image.Order,
        image.CreatedAt);
}

public sealed record ProductSpecReadDto(
    int Id,
    int Product,
    string Name,
    string Value,
    string Unit,
    int Order)
{
    public static ProductSpecReadDto FromSpec(ProductSpec spec) => new(
        spec.Id,
        spec.ProductId,
        spec.Key,
        spec.Value,
        spec.Unit,
        spec.Order);
}

public sealed record ProductListReadDto(
    int Id,
    string Name,
    string Slug,
    CategoryReadDto Category,
    BrandReadDto? Brand,
    string ProductType,
    string Condition,
    string ShortDescription,
    decimal? Price,
    bool PriceVisible,
    string StockStatus,
    bool IsFeatured,
    bool IsPublished,
    ProductImageReadDto? MainImage,
    DateTimeOffset UpdatedAt)
{
    public static ProductListReadDto FromProduct(Product product) => new(
        product.Id,
        product.Name,
        product.Slug,
        CategoryReadDto.FromCategory(product.Category),
        product.Brand is null ? null : BrandReadDto.FromBrand(product.Brand),
        product.ProductType,
        product.Condition,
        product.ShortDescription,
        product.Price,
        product.PriceVisible,
        product.StockStatus,
        product.IsFeatured,
        product.IsPublished,
        product.Images
            .OrderByDescending(image => image.IsMain)
            .ThenBy(image => image.Order)
            .ThenBy(image => image.Id)
            .Select(ProductImageReadDto.FromImage)
            .FirstOrDefault(),
        product.UpdatedAt);
}

public sealed record ProductDetailReadDto(
    int Id,
    string Name,
    string Slug,
    CategoryReadDto Category,
    BrandReadDto? Brand,
    SupplierReadDto? Supplier,
    string ProductType,
    string Condition,
    string ShortDescription,
    string Description,
    string Model,
    string Sku,
    int? Year,
    int? HoursMeter,
    decimal? Price,
    bool PriceVisible,
    string StockStatus,
    bool IsFeatured,
    bool IsPublished,
    ProductImageReadDto? MainImage,
    IReadOnlyList<ProductImageReadDto> Images,
    IReadOnlyList<ProductSpecReadDto> Specs,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static ProductDetailReadDto FromProduct(Product product)
    {
        var images = product.Images
            .OrderByDescending(image => image.IsMain)
            .ThenBy(image => image.Order)
            .ThenBy(image => image.Id)
            .Select(ProductImageReadDto.FromImage)
            .ToList();

        return new ProductDetailReadDto(
            product.Id,
            product.Name,
            product.Slug,
            CategoryReadDto.FromCategory(product.Category),
            product.Brand is null ? null : BrandReadDto.FromBrand(product.Brand),
            product.Supplier is null ? null : SupplierReadDto.FromSupplier(product.Supplier),
            product.ProductType,
            product.Condition,
            product.ShortDescription,
            product.Description,
            product.Model,
            product.Sku,
            product.Year,
            product.HoursMeter,
            product.Price,
            product.PriceVisible,
            product.StockStatus,
            product.IsFeatured,
            product.IsPublished,
            images.FirstOrDefault(),
            images,
            product.Specs
                .OrderBy(spec => spec.Order)
                .ThenBy(spec => spec.Id)
                .Select(ProductSpecReadDto.FromSpec)
                .ToList(),
            product.CreatedAt,
            product.UpdatedAt);
    }
}

public sealed record PromotionReadDto(
    int Id,
    string Title,
    string Subtitle,
    ProductListReadDto? Product,
    string? Image,
    string ButtonText,
    string ButtonUrl,
    bool IsActive,
    int Order,
    DateTimeOffset? StartsAt,
    DateTimeOffset? EndsAt,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static PromotionReadDto FromPromotion(Promotion promotion) => new(
        promotion.Id,
        promotion.Title,
        promotion.Subtitle,
        promotion.Product is null ? null : ProductListReadDto.FromProduct(promotion.Product),
        promotion.Image,
        promotion.ButtonText,
        promotion.ButtonUrl,
        promotion.IsActive,
        promotion.Order,
        promotion.StartsAt,
        promotion.EndsAt,
        promotion.CreatedAt,
        promotion.UpdatedAt);
}

public sealed record QuoteRequestReadDto(
    int Id,
    int? Product,
    string ProductName,
    string CustomerName,
    string CustomerPhone,
    string CustomerEmail,
    string CompanyName,
    string City,
    string PreferredContactMethod,
    string Message,
    string Status,
    string InternalNotes,
    string SellerResponse,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt,
    DateTimeOffset? ContactedAt,
    DateTimeOffset? QuotedAt,
    DateTimeOffset? ClosedAt)
{
    public static QuoteRequestReadDto FromQuoteRequest(QuoteRequest quote) => new(
        quote.Id,
        quote.ProductId,
        quote.Product?.Name ?? string.Empty,
        quote.CustomerName,
        quote.CustomerPhone,
        quote.CustomerEmail,
        quote.CompanyName,
        quote.City,
        quote.PreferredContactMethod,
        quote.Message,
        quote.Status,
        quote.InternalNotes,
        quote.SellerResponse,
        quote.CreatedAt,
        quote.UpdatedAt,
        quote.ContactedAt,
        quote.QuotedAt,
        quote.ClosedAt);
}

public sealed record HomeSectionItemReadDto(
    int Id,
    string Section,
    string SectionLabel,
    int Position,
    ProductListReadDto Product,
    bool IsActive,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static HomeSectionItemReadDto FromHomeSectionItem(HomeSectionItem item) => new(
        item.Id,
        item.Section,
        GetSectionLabel(item.Section),
        item.Position,
        ProductListReadDto.FromProduct(item.Product),
        item.IsActive,
        item.CreatedAt,
        item.UpdatedAt);

    private static string GetSectionLabel(string section) => section switch
    {
        HomeSections.MachineryPromotions => "Promociones en maquinarias",
        HomeSections.SparePartsOffers => "Oferta en repuestos",
        HomeSections.RepairServices => "Servicios de reparación",
        _ => section
    };
}
