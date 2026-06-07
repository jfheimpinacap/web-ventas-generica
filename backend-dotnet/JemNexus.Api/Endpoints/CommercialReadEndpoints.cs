using JemNexus.Api.Data;
using JemNexus.Api.Dtos;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static class CommercialReadEndpoints
{
    private const string CommercialReadPolicy = "RequireCommercialRead";

    public static IEndpointRouteBuilder MapCommercialReadEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api")
            .RequireAuthorization(CommercialReadPolicy)
            .WithTags("Commercial read-only");

        group.MapGet("/products", GetProductsAsync).WithName("CommercialProductsList").WithOpenApi();
        group.MapGet("/products/{idOrSlug}", GetProductAsync).WithName("CommercialProductsDetail").WithOpenApi();

        group.MapGet("/categories", GetCategoriesAsync).WithName("CommercialCategoriesList").WithOpenApi();
        group.MapGet("/categories/{id:int}", GetCategoryAsync).WithName("CommercialCategoriesDetail").WithOpenApi();

        group.MapGet("/brands", GetBrandsAsync).WithName("CommercialBrandsList").WithOpenApi();
        group.MapGet("/brands/{id:int}", GetBrandAsync).WithName("CommercialBrandsDetail").WithOpenApi();

        group.MapGet("/suppliers", GetSuppliersAsync).WithName("CommercialSuppliersList").WithOpenApi();
        group.MapGet("/suppliers/{id:int}", GetSupplierAsync).WithName("CommercialSuppliersDetail").WithOpenApi();

        group.MapGet("/promotions", GetPromotionsAsync).WithName("CommercialPromotionsList").WithOpenApi();
        group.MapGet("/promotions/{id:int}", GetPromotionAsync).WithName("CommercialPromotionsDetail").WithOpenApi();

        group.MapGet("/quote-requests", GetQuoteRequestsAsync).WithName("CommercialQuoteRequestsList").WithOpenApi();
        group.MapGet("/quote-requests/{id:int}", GetQuoteRequestAsync).WithName("CommercialQuoteRequestsDetail").WithOpenApi();

        group.MapGet("/home-section-items", GetHomeSectionItemsAsync).WithName("CommercialHomeSectionItemsList").WithOpenApi();
        group.MapGet("/home-section-items/{id:int}", GetHomeSectionItemAsync).WithName("CommercialHomeSectionItemsDetail").WithOpenApi();

        group.MapGet("/product-images", GetProductImagesAsync).WithName("CommercialProductImagesList").WithOpenApi();
        group.MapGet("/product-images/{id:int}", GetProductImageAsync).WithName("CommercialProductImagesDetail").WithOpenApi();

        group.MapGet("/product-specs", GetProductSpecsAsync).WithName("CommercialProductSpecsList").WithOpenApi();
        group.MapGet("/product-specs/{id:int}", GetProductSpecAsync).WithName("CommercialProductSpecsDetail").WithOpenApi();

        return app;
    }

    private static async Task<IResult> GetProductsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "category")] string? category,
        [FromQuery(Name = "brand")] string? brand,
        [FromQuery(Name = "product_type")] string? productType,
        [FromQuery(Name = "condition")] string? condition,
        [FromQuery(Name = "stock_status")] string? stockStatus,
        [FromQuery(Name = "is_featured")] bool? isFeatured,
        [FromQuery(Name = "is_published")] bool? isPublished,
        [FromQuery(Name = "include_unpublished")] bool? includeUnpublished,
        [FromQuery(Name = "ordering")] string? ordering,
        CancellationToken cancellationToken)
    {
        var query = ProductReadQuery(dbContext.Products);

        if (includeUnpublished != true)
        {
            query = query.Where(product => product.IsPublished);
        }

        if (isPublished.HasValue)
        {
            query = query.Where(product => product.IsPublished == isPublished.Value);
        }

        if (isFeatured.HasValue)
        {
            query = query.Where(product => product.IsFeatured == isFeatured.Value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(product =>
                product.Name.ToLower().Contains(term)
                || product.Slug.ToLower().Contains(term)
                || product.Sku.ToLower().Contains(term)
                || product.Model.ToLower().Contains(term)
                || product.ShortDescription.ToLower().Contains(term));
        }

        if (!string.IsNullOrWhiteSpace(category))
        {
            var value = category.Trim();
            if (int.TryParse(value, out var categoryId))
            {
                query = query.Where(product => product.CategoryId == categoryId);
            }
            else
            {
                var slug = value.ToLower();
                query = query.Where(product => product.Category.Slug.ToLower() == slug);
            }
        }

        if (!string.IsNullOrWhiteSpace(brand))
        {
            var value = brand.Trim();
            if (int.TryParse(value, out var brandId))
            {
                query = query.Where(product => product.BrandId == brandId);
            }
            else
            {
                var slug = value.ToLower();
                query = query.Where(product => product.Brand != null && product.Brand.Slug.ToLower() == slug);
            }
        }

        if (!string.IsNullOrWhiteSpace(productType))
        {
            var value = productType.Trim();
            query = query.Where(product => product.ProductType == value);
        }

        if (!string.IsNullOrWhiteSpace(condition))
        {
            var value = condition.Trim();
            query = query.Where(product => product.Condition == value);
        }

        if (!string.IsNullOrWhiteSpace(stockStatus))
        {
            var value = stockStatus.Trim();
            query = query.Where(product => product.StockStatus == value);
        }

        query = (ordering ?? string.Empty) switch
        {
            "name" => query.OrderBy(product => product.Name),
            "-name" => query.OrderByDescending(product => product.Name),
            "created_at" => query.OrderBy(product => product.CreatedAt),
            "-created_at" => query.OrderByDescending(product => product.CreatedAt),
            "updated_at" => query.OrderBy(product => product.UpdatedAt),
            "-updated_at" => query.OrderByDescending(product => product.UpdatedAt),
            "price" => query.OrderBy(product => product.Price),
            "-price" => query.OrderByDescending(product => product.Price),
            _ => query.OrderByDescending(product => product.UpdatedAt).ThenBy(product => product.Name)
        };

        var products = await query.ToListAsync(cancellationToken);
        return Results.Ok(products.Select(ProductListReadDto.FromProduct).ToList());
    }

    private static async Task<IResult> GetProductAsync(string idOrSlug, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var query = ProductReadQuery(dbContext.Products);
        var product = int.TryParse(idOrSlug, out var id)
            ? await query.FirstOrDefaultAsync(product => product.Id == id, cancellationToken)
            : await query.FirstOrDefaultAsync(product => product.Slug == idOrSlug, cancellationToken);

        return product is null ? Results.NotFound() : Results.Ok(ProductDetailReadDto.FromProduct(product));
    }

    private static async Task<IResult> GetCategoriesAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "is_active")] bool? isActive,
        [FromQuery(Name = "include_inactive")] bool? includeInactive,
        CancellationToken cancellationToken)
    {
        var query = dbContext.Categories.AsNoTracking().AsQueryable();
        if (includeInactive != true)
        {
            query = query.Where(category => category.IsActive);
        }

        if (isActive.HasValue)
        {
            query = query.Where(category => category.IsActive == isActive.Value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(category => category.Name.ToLower().Contains(term) || category.Slug.ToLower().Contains(term));
        }

        var categories = await query.OrderBy(category => category.Order).ThenBy(category => category.Name).ToListAsync(cancellationToken);
        return Results.Ok(categories.Select(CategoryReadDto.FromCategory).ToList());
    }

    private static async Task<IResult> GetCategoryAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var category = await dbContext.Categories.AsNoTracking().FirstOrDefaultAsync(category => category.Id == id, cancellationToken);
        return category is null ? Results.NotFound() : Results.Ok(CategoryReadDto.FromCategory(category));
    }

    private static async Task<IResult> GetBrandsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "is_active")] bool? isActive,
        [FromQuery(Name = "include_inactive")] bool? includeInactive,
        CancellationToken cancellationToken)
    {
        var query = dbContext.Brands.AsNoTracking().AsQueryable();
        if (includeInactive != true)
        {
            query = query.Where(brand => brand.IsActive);
        }

        if (isActive.HasValue)
        {
            query = query.Where(brand => brand.IsActive == isActive.Value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(brand => brand.Name.ToLower().Contains(term) || brand.Slug.ToLower().Contains(term));
        }

        var brands = await query.OrderBy(brand => brand.Name).ToListAsync(cancellationToken);
        return Results.Ok(brands.Select(BrandReadDto.FromBrand).ToList());
    }

    private static async Task<IResult> GetBrandAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var brand = await dbContext.Brands.AsNoTracking().FirstOrDefaultAsync(brand => brand.Id == id, cancellationToken);
        return brand is null ? Results.NotFound() : Results.Ok(BrandReadDto.FromBrand(brand));
    }

    private static async Task<IResult> GetSuppliersAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "is_active")] bool? isActive,
        [FromQuery(Name = "include_inactive")] bool? includeInactive,
        CancellationToken cancellationToken)
    {
        var query = dbContext.Suppliers.AsNoTracking().AsQueryable();
        if (includeInactive != true)
        {
            query = query.Where(supplier => supplier.IsActive);
        }

        if (isActive.HasValue)
        {
            query = query.Where(supplier => supplier.IsActive == isActive.Value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(supplier =>
                supplier.Name.ToLower().Contains(term)
                || supplier.ContactName.ToLower().Contains(term)
                || supplier.Email.ToLower().Contains(term)
                || supplier.Phone.ToLower().Contains(term));
        }

        var suppliers = await query.OrderBy(supplier => supplier.Name).ToListAsync(cancellationToken);
        return Results.Ok(suppliers.Select(SupplierReadDto.FromSupplier).ToList());
    }

    private static async Task<IResult> GetSupplierAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var supplier = await dbContext.Suppliers.AsNoTracking().FirstOrDefaultAsync(supplier => supplier.Id == id, cancellationToken);
        return supplier is null ? Results.NotFound() : Results.Ok(SupplierReadDto.FromSupplier(supplier));
    }

    private static async Task<IResult> GetPromotionsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "is_active")] bool? isActive,
        [FromQuery(Name = "include_inactive")] bool? includeInactive,
        CancellationToken cancellationToken)
    {
        var query = PromotionReadQuery(dbContext.Promotions);
        if (includeInactive != true)
        {
            query = query.Where(promotion => promotion.IsActive);
        }

        if (isActive.HasValue)
        {
            query = query.Where(promotion => promotion.IsActive == isActive.Value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(promotion => promotion.Title.ToLower().Contains(term) || promotion.Subtitle.ToLower().Contains(term));
        }

        var promotions = await query.OrderBy(promotion => promotion.Order).ThenByDescending(promotion => promotion.UpdatedAt).ToListAsync(cancellationToken);
        return Results.Ok(promotions.Select(PromotionReadDto.FromPromotion).ToList());
    }

    private static async Task<IResult> GetPromotionAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var promotion = await PromotionReadQuery(dbContext.Promotions).FirstOrDefaultAsync(promotion => promotion.Id == id, cancellationToken);
        return promotion is null ? Results.NotFound() : Results.Ok(PromotionReadDto.FromPromotion(promotion));
    }

    private static async Task<IResult> GetQuoteRequestsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "status")] string? status,
        [FromQuery(Name = "product")] int? product,
        [FromQuery(Name = "ordering")] string? ordering,
        CancellationToken cancellationToken)
    {
        var query = dbContext.QuoteRequests
            .AsNoTracking()
            .Include(quote => quote.Product)
            .AsQueryable();

        if (product.HasValue)
        {
            query = query.Where(quote => quote.ProductId == product.Value);
        }

        if (!string.IsNullOrWhiteSpace(status))
        {
            var value = status.Trim();
            query = query.Where(quote => quote.Status == value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(quote =>
                quote.CustomerName.ToLower().Contains(term)
                || quote.CustomerPhone.ToLower().Contains(term)
                || quote.CustomerEmail.ToLower().Contains(term)
                || quote.CompanyName.ToLower().Contains(term)
                || quote.City.ToLower().Contains(term)
                || quote.Message.ToLower().Contains(term));
        }

        query = (ordering ?? string.Empty) switch
        {
            "created_at" => query.OrderBy(quote => quote.CreatedAt),
            "-created_at" => query.OrderByDescending(quote => quote.CreatedAt),
            "updated_at" => query.OrderBy(quote => quote.UpdatedAt),
            "-updated_at" => query.OrderByDescending(quote => quote.UpdatedAt),
            "status" => query.OrderBy(quote => quote.Status).ThenByDescending(quote => quote.CreatedAt),
            "-status" => query.OrderByDescending(quote => quote.Status).ThenByDescending(quote => quote.CreatedAt),
            _ => query.OrderByDescending(quote => quote.CreatedAt)
        };

        var quotes = await query.ToListAsync(cancellationToken);
        return Results.Ok(quotes.Select(QuoteRequestReadDto.FromQuoteRequest).ToList());
    }

    private static async Task<IResult> GetQuoteRequestAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var quote = await dbContext.QuoteRequests
            .AsNoTracking()
            .Include(quote => quote.Product)
            .FirstOrDefaultAsync(quote => quote.Id == id, cancellationToken);

        return quote is null ? Results.NotFound() : Results.Ok(QuoteRequestReadDto.FromQuoteRequest(quote));
    }

    private static async Task<IResult> GetHomeSectionItemsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "section")] string? section,
        [FromQuery(Name = "is_active")] bool? isActive,
        [FromQuery(Name = "include_inactive")] bool? includeInactive,
        CancellationToken cancellationToken)
    {
        var query = dbContext.HomeSectionItems
            .AsNoTracking()
            .Include(item => item.Product).ThenInclude(product => product.Category)
            .Include(item => item.Product).ThenInclude(product => product.Brand)
            .Include(item => item.Product).ThenInclude(product => product.Images)
            .AsQueryable();

        if (includeInactive != true)
        {
            query = query.Where(item => item.IsActive);
        }

        if (isActive.HasValue)
        {
            query = query.Where(item => item.IsActive == isActive.Value);
        }

        if (!string.IsNullOrWhiteSpace(section))
        {
            var value = section.Trim();
            query = query.Where(item => item.Section == value);
        }

        var items = await query.OrderBy(item => item.Section).ThenBy(item => item.Position).ToListAsync(cancellationToken);
        return Results.Ok(items.Select(HomeSectionItemReadDto.FromHomeSectionItem).ToList());
    }

    private static async Task<IResult> GetHomeSectionItemAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var item = await dbContext.HomeSectionItems
            .AsNoTracking()
            .Include(item => item.Product).ThenInclude(product => product.Category)
            .Include(item => item.Product).ThenInclude(product => product.Brand)
            .Include(item => item.Product).ThenInclude(product => product.Images)
            .FirstOrDefaultAsync(item => item.Id == id, cancellationToken);

        return item is null ? Results.NotFound() : Results.Ok(HomeSectionItemReadDto.FromHomeSectionItem(item));
    }

    private static async Task<IResult> GetProductImagesAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "product")] int? product,
        CancellationToken cancellationToken)
    {
        var query = dbContext.ProductImages.AsNoTracking().AsQueryable();
        if (product.HasValue)
        {
            query = query.Where(image => image.ProductId == product.Value);
        }

        var images = await query.OrderBy(image => image.ProductId).ThenBy(image => image.Order).ThenBy(image => image.Id).ToListAsync(cancellationToken);
        return Results.Ok(images.Select(ProductImageReadDto.FromImage).ToList());
    }

    private static async Task<IResult> GetProductImageAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var image = await dbContext.ProductImages.AsNoTracking().FirstOrDefaultAsync(image => image.Id == id, cancellationToken);
        return image is null ? Results.NotFound() : Results.Ok(ProductImageReadDto.FromImage(image));
    }

    private static async Task<IResult> GetProductSpecsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "product")] int? product,
        CancellationToken cancellationToken)
    {
        var query = dbContext.ProductSpecs.AsNoTracking().AsQueryable();
        if (product.HasValue)
        {
            query = query.Where(spec => spec.ProductId == product.Value);
        }

        var specs = await query.OrderBy(spec => spec.ProductId).ThenBy(spec => spec.Order).ThenBy(spec => spec.Id).ToListAsync(cancellationToken);
        return Results.Ok(specs.Select(ProductSpecReadDto.FromSpec).ToList());
    }

    private static async Task<IResult> GetProductSpecAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var spec = await dbContext.ProductSpecs.AsNoTracking().FirstOrDefaultAsync(spec => spec.Id == id, cancellationToken);
        return spec is null ? Results.NotFound() : Results.Ok(ProductSpecReadDto.FromSpec(spec));
    }

    private static IQueryable<JemNexus.Api.Models.Product> ProductReadQuery(IQueryable<JemNexus.Api.Models.Product> products) => products
        .AsNoTracking()
        .Include(product => product.Category)
        .Include(product => product.Brand)
        .Include(product => product.Supplier)
        .Include(product => product.Images)
        .Include(product => product.Specs);

    private static IQueryable<JemNexus.Api.Models.Promotion> PromotionReadQuery(IQueryable<JemNexus.Api.Models.Promotion> promotions) => promotions
        .AsNoTracking()
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Category)
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Brand)
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Images);
}
