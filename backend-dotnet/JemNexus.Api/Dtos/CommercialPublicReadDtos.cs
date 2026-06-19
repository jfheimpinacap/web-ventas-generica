using JemNexus.Api.Models;

namespace JemNexus.Api.Dtos;

public sealed record PublicCategoryReadDto(
    int Id,
    string Name,
    string Slug,
    int? Parent,
    string ProductType,
    string Description,
    int Order)
{
    public static PublicCategoryReadDto FromCategory(Category category) => new(
        category.Id,
        category.Name,
        category.Slug,
        category.ParentId,
        category.ProductType,
        category.Description,
        category.Order);
}

public sealed record PublicBrandReadDto(
    int Id,
    string Name,
    string Slug,
    string? Logo,
    string Description)
{
    public static PublicBrandReadDto FromBrand(Brand brand) => new(
        brand.Id,
        brand.Name,
        brand.Slug,
        brand.Logo,
        brand.Description);
}

public sealed record PublicProductImageReadDto(
    int Id,
    int Product,
    string Image,
    string AltText,
    bool IsMain,
    int Order)
{
    public static PublicProductImageReadDto FromImage(ProductImage image) => new(
        image.Id,
        image.ProductId,
        image.Image,
        image.AltText,
        image.IsMain,
        image.Order);
}

public sealed record PublicProductSpecReadDto(
    int Id,
    int Product,
    string Name,
    string Value,
    string Unit,
    int Order)
{
    public static PublicProductSpecReadDto FromSpec(ProductSpec spec) => new(
        spec.Id,
        spec.ProductId,
        spec.Key,
        spec.Value,
        spec.Unit,
        spec.Order);
}

public sealed record PublicProductListReadDto(
    int Id,
    string Name,
    string Slug,
    PublicCategoryReadDto Category,
    PublicBrandReadDto? Brand,
    string ProductType,
    string Condition,
    string ShortDescription,
    decimal? Price,
    string PriceCurrency,
    string PriceTaxMode,
    bool PriceVisible,
    string StockStatus,
    bool IsFeatured,
    PublicProductImageReadDto? MainImage)
{
    public static PublicProductListReadDto FromProduct(Product product) => new(
        product.Id,
        product.Name,
        product.Slug,
        PublicCategoryReadDto.FromCategory(product.Category),
        product.Brand is null ? null : PublicBrandReadDto.FromBrand(product.Brand),
        product.ProductType,
        product.Condition,
        product.ShortDescription,
        product.Price,
        product.PriceCurrency,
        product.PriceTaxMode,
        product.PriceVisible,
        product.StockStatus,
        product.IsFeatured,
        product.Images
            .OrderByDescending(image => image.IsMain)
            .ThenBy(image => image.Order)
            .ThenBy(image => image.Id)
            .Select(PublicProductImageReadDto.FromImage)
            .FirstOrDefault());
}

public sealed record PublicProductDetailReadDto(
    int Id,
    string Name,
    string Slug,
    PublicCategoryReadDto Category,
    PublicBrandReadDto? Brand,
    string ProductType,
    string Condition,
    string ShortDescription,
    string Description,
    string Model,
    string Sku,
    int? Year,
    int? HoursMeter,
    decimal? Price,
    string PriceCurrency,
    string PriceTaxMode,
    bool PriceVisible,
    string StockStatus,
    bool IsFeatured,
    PublicProductImageReadDto? MainImage,
    IReadOnlyList<PublicProductImageReadDto> Images,
    IReadOnlyList<PublicProductSpecReadDto> Specs)
{
    public static PublicProductDetailReadDto FromProduct(Product product)
    {
        var images = product.Images
            .OrderByDescending(image => image.IsMain)
            .ThenBy(image => image.Order)
            .ThenBy(image => image.Id)
            .Select(PublicProductImageReadDto.FromImage)
            .ToList();

        return new PublicProductDetailReadDto(
            product.Id,
            product.Name,
            product.Slug,
            PublicCategoryReadDto.FromCategory(product.Category),
            product.Brand is null ? null : PublicBrandReadDto.FromBrand(product.Brand),
            product.ProductType,
            product.Condition,
            product.ShortDescription,
            product.Description,
            product.Model,
            product.Sku,
            product.Year,
            product.HoursMeter,
            product.Price,
            product.PriceCurrency,
            product.PriceTaxMode,
            product.PriceVisible,
            product.StockStatus,
            product.IsFeatured,
            images.FirstOrDefault(),
            images,
            product.Specs
                .OrderBy(spec => spec.Order)
                .ThenBy(spec => spec.Id)
                .Select(PublicProductSpecReadDto.FromSpec)
                .ToList());
    }
}

public sealed record PublicPromotionReadDto(
    int Id,
    string Title,
    string Subtitle,
    PublicProductListReadDto? Product,
    string? Image,
    string ButtonText,
    string ButtonUrl,
    int Order,
    DateTimeOffset? StartsAt,
    DateTimeOffset? EndsAt)
{
    public static PublicPromotionReadDto FromPromotion(Promotion promotion) => new(
        promotion.Id,
        promotion.Title,
        promotion.Subtitle,
        promotion.Product is null ? null : PublicProductListReadDto.FromProduct(promotion.Product),
        promotion.Image,
        promotion.ButtonText,
        promotion.ButtonUrl,
        promotion.Order,
        promotion.StartsAt,
        promotion.EndsAt);
}

public sealed record PublicHomeSectionItemReadDto(
    int Id,
    string Section,
    string SectionLabel,
    int Position,
    PublicProductListReadDto Product)
{
    public static PublicHomeSectionItemReadDto FromHomeSectionItem(HomeSectionItem item) => new(
        item.Id,
        item.Section,
        GetSectionLabel(item.Section),
        item.Position,
        PublicProductListReadDto.FromProduct(item.Product));

    private static string GetSectionLabel(string section) => section switch
    {
        HomeSections.MachineryPromotions => "Promociones en maquinarias",
        HomeSections.SparePartsOffers => "Oferta en repuestos",
        HomeSections.RepairServices => "Servicios de reparación",
        _ => section
    };
}
