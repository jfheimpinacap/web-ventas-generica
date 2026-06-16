using JemNexus.Api.Data;
using JemNexus.Api.Dtos;
using JemNexus.Api.Models;
using JemNexus.Api.Services.Notifications;
using JemNexus.Api.Validation;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static class CommercialPublicReadEndpoints
{
    private static readonly ISet<string> PublicProductTypes = new HashSet<string>(StringComparer.Ordinal)
    {
        ProductTypes.Machinery,
        ProductTypes.SparePart,
        ProductTypes.Service
    };

    private static readonly ISet<string> PublicProductConditions = new HashSet<string>(StringComparer.Ordinal)
    {
        ProductConditions.New,
        ProductConditions.Used,
        ProductConditions.Refurbished,
        ProductConditions.NotApplicable
    };

    private static readonly ISet<string> PublicStockStatuses = new HashSet<string>(StringComparer.Ordinal)
    {
        StockStatuses.Available,
        StockStatuses.OnRequest,
        StockStatuses.Sold,
        StockStatuses.Reserved
    };

    public static IEndpointRouteBuilder MapCommercialPublicReadEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/public")
            .AllowAnonymous()
            .WithTags("Commercial public read-only");

        group.MapGet("/products", GetProductsAsync).WithName("CommercialPublicProductsList").WithOpenApi();
        group.MapGet("/products/{idOrSlug}", GetProductAsync).WithName("CommercialPublicProductsDetail").WithOpenApi();

        group.MapGet("/categories", GetCategoriesAsync).WithName("CommercialPublicCategoriesList").WithOpenApi();
        group.MapGet("/brands", GetBrandsAsync).WithName("CommercialPublicBrandsList").WithOpenApi();
        group.MapGet("/promotions", GetPromotionsAsync).WithName("CommercialPublicPromotionsList").WithOpenApi();
        group.MapPost("/quote-requests", CreateQuoteRequestAsync).WithName("CommercialPublicQuoteRequestsCreate").WithOpenApi();
        group.MapGet("/home-section-items", GetHomeSectionItemsAsync).WithName("CommercialPublicHomeSectionItemsList").WithOpenApi();
        group.MapGet("/product-images", GetProductImagesAsync).WithName("CommercialPublicProductImagesList").WithOpenApi();
        group.MapGet("/product-specs", GetProductSpecsAsync).WithName("CommercialPublicProductSpecsList").WithOpenApi();

        return app;
    }

    private static async Task<IResult> CreateQuoteRequestAsync(
        QuoteRequestPublicCreateDto request,
        JemNexusDbContext dbContext,
        IQuoteNotificationService quoteNotificationService,
        ILoggerFactory loggerFactory,
        CancellationToken cancellationToken)
    {
        var productId = request.ProductId ?? request.Product;
        Product? product = null;
        if (productId.HasValue)
        {
            product = await dbContext.Products
                .FirstOrDefaultAsync(candidate => candidate.Id == productId.Value && candidate.IsPublished, cancellationToken);
            if (product is null) return Results.BadRequest(new { detail = "product does not exist." });
        }

        var now = DateTimeOffset.UtcNow;
        var quote = new QuoteRequest
        {
            ProductId = productId,
            CustomerName = Clean(request.CustomerName),
            CustomerPhone = Clean(request.CustomerPhone),
            CustomerEmail = Clean(request.CustomerEmail),
            CompanyName = Clean(request.CompanyName),
            City = Clean(request.City),
            PreferredContactMethod = Clean(request.PreferredContactMethod),
            Message = Clean(request.Message),
            Status = QuoteStatuses.New,
            CreatedAt = now,
            UpdatedAt = now
        };

        var validationErrors = CommercialValidation.ValidateQuoteRequest(quote);
        if (validationErrors.Count > 0) return Results.BadRequest(new { detail = validationErrors });

        dbContext.QuoteRequests.Add(quote);
        await dbContext.SaveChangesAsync(cancellationToken);

        quote.Product = product;
        try
        {
            var notificationResult = await quoteNotificationService.SendNewQuoteRequestAsync(quote, cancellationToken);
            if (!notificationResult.Success)
            {
                var logger = loggerFactory.CreateLogger(nameof(CommercialPublicReadEndpoints));
                logger.LogWarning(
                    "Quote request {QuoteRequestId} was saved but seller email notification did not complete. Code: {ErrorCode}. Message: {ErrorMessage}.",
                    quote.Id,
                    notificationResult.ErrorCode,
                    notificationResult.ErrorMessage);
            }
        }
        catch (Exception exception)
        {
            var logger = loggerFactory.CreateLogger(nameof(CommercialPublicReadEndpoints));
            logger.LogError(exception, "Quote request {QuoteRequestId} was saved but seller email notification failed unexpectedly.", quote.Id);
        }

        return Results.Created($"/api/quote-requests/{quote.Id}", QuoteRequestReadDto.FromQuoteRequest(quote));
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
        [FromQuery(Name = "ordering")] string? ordering,
        CancellationToken cancellationToken)
    {
        var query = ApplyPublicProductFilters(PublicProductReadQuery(dbContext.Products));

        if (isFeatured.HasValue)
        {
            query = query.Where(product => product.IsFeatured == isFeatured.Value);
        }

        query = ApplyPublicProductSearchAndFilters(query, search, category, brand, productType, condition, stockStatus);
        query = ApplyPublicProductOrdering(query, ordering);

        var products = await query.ToListAsync(cancellationToken);
        return Results.Ok(products.Select(PublicProductListReadDto.FromProduct).ToList());
    }

    private static async Task<IResult> GetProductAsync(string idOrSlug, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var query = ApplyPublicProductFilters(PublicProductReadQuery(dbContext.Products));
        var product = int.TryParse(idOrSlug, out var id)
            ? await query.FirstOrDefaultAsync(product => product.Id == id, cancellationToken)
            : await query.FirstOrDefaultAsync(product => product.Slug == idOrSlug, cancellationToken);

        return product is null ? Results.NotFound() : Results.Ok(PublicProductDetailReadDto.FromProduct(product));
    }

    private static async Task<IResult> GetCategoriesAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        [FromQuery(Name = "product_type")] string? productType,
        CancellationToken cancellationToken)
    {
        var query = dbContext.Categories.AsNoTracking().Where(category => category.IsActive);

        if (!string.IsNullOrWhiteSpace(productType))
        {
            var value = productType.Trim();
            query = query.Where(category => category.ProductType == value);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(category => category.Name.ToLower().Contains(term) || category.Slug.ToLower().Contains(term));
        }

        var categories = await query.OrderBy(category => category.Order).ThenBy(category => category.Name).ToListAsync(cancellationToken);
        return Results.Ok(categories.Select(PublicCategoryReadDto.FromCategory).ToList());
    }

    private static async Task<IResult> GetBrandsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        CancellationToken cancellationToken)
    {
        var query = dbContext.Brands.AsNoTracking().Where(brand => brand.IsActive);

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(brand => brand.Name.ToLower().Contains(term) || brand.Slug.ToLower().Contains(term));
        }

        var brands = await query.OrderBy(brand => brand.Name).ToListAsync(cancellationToken);
        return Results.Ok(brands.Select(PublicBrandReadDto.FromBrand).ToList());
    }

    private static async Task<IResult> GetPromotionsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "search")] string? search,
        CancellationToken cancellationToken)
    {
        var now = DateTimeOffset.UtcNow;
        var query = PublicPromotionReadQuery(dbContext.Promotions)
            .Where(promotion => promotion.IsActive)
            .Where(promotion => promotion.StartsAt == null || promotion.StartsAt <= now)
            .Where(promotion => promotion.EndsAt == null || promotion.EndsAt >= now)
            .Where(promotion => promotion.Product == null
                || (promotion.Product.IsPublished
                    && promotion.Product.Category.IsActive
                    && (promotion.Product.Brand == null || promotion.Product.Brand.IsActive)));

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(promotion => promotion.Title.ToLower().Contains(term) || promotion.Subtitle.ToLower().Contains(term));
        }

        var promotions = await query.OrderBy(promotion => promotion.Order).ThenByDescending(promotion => promotion.UpdatedAt).ToListAsync(cancellationToken);
        return Results.Ok(promotions.Select(PublicPromotionReadDto.FromPromotion).ToList());
    }

    private static async Task<IResult> GetHomeSectionItemsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "section")] string? section,
        CancellationToken cancellationToken)
    {
        var query = dbContext.HomeSectionItems
            .AsNoTracking()
            .Include(item => item.Product).ThenInclude(product => product.Category)
            .Include(item => item.Product).ThenInclude(product => product.Brand)
            .Include(item => item.Product).ThenInclude(product => product.Images)
            .Where(item => item.IsActive)
            .Where(item => item.Product.IsPublished)
            .Where(item => item.Product.Category.IsActive)
            .Where(item => item.Product.Brand == null || item.Product.Brand.IsActive);

        if (!string.IsNullOrWhiteSpace(section))
        {
            var value = section.Trim();
            query = query.Where(item => item.Section == value);
        }

        var items = await query.OrderBy(item => item.Section).ThenBy(item => item.Position).ToListAsync(cancellationToken);
        return Results.Ok(items.Select(PublicHomeSectionItemReadDto.FromHomeSectionItem).ToList());
    }

    private static async Task<IResult> GetProductImagesAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "product")] int? product,
        CancellationToken cancellationToken)
    {
        var query = dbContext.ProductImages
            .AsNoTracking()
            .Include(image => image.Product).ThenInclude(product => product.Category)
            .Include(image => image.Product).ThenInclude(product => product.Brand)
            .Where(image => image.Product.IsPublished)
            .Where(image => image.Product.Category.IsActive)
            .Where(image => image.Product.Brand == null || image.Product.Brand.IsActive);

        if (product.HasValue)
        {
            query = query.Where(image => image.ProductId == product.Value);
        }

        var images = await query.OrderBy(image => image.ProductId).ThenBy(image => image.Order).ThenBy(image => image.Id).ToListAsync(cancellationToken);
        return Results.Ok(images.Select(PublicProductImageReadDto.FromImage).ToList());
    }

    private static async Task<IResult> GetProductSpecsAsync(
        JemNexusDbContext dbContext,
        [FromQuery(Name = "product")] int? product,
        CancellationToken cancellationToken)
    {
        var query = dbContext.ProductSpecs
            .AsNoTracking()
            .Include(spec => spec.Product).ThenInclude(product => product.Category)
            .Include(spec => spec.Product).ThenInclude(product => product.Brand)
            .Where(spec => spec.Product.IsPublished)
            .Where(spec => spec.Product.Category.IsActive)
            .Where(spec => spec.Product.Brand == null || spec.Product.Brand.IsActive);

        if (product.HasValue)
        {
            query = query.Where(spec => spec.ProductId == product.Value);
        }

        var specs = await query.OrderBy(spec => spec.ProductId).ThenBy(spec => spec.Order).ThenBy(spec => spec.Id).ToListAsync(cancellationToken);
        return Results.Ok(specs.Select(PublicProductSpecReadDto.FromSpec).ToList());
    }

    private static IQueryable<Product> ApplyPublicProductSearchAndFilters(
        IQueryable<Product> query,
        string? search,
        string? category,
        string? brand,
        string? productType,
        string? condition,
        string? stockStatus)
    {
        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLower();
            query = query.Where(product =>
                product.Name.ToLower().Contains(term)
                || product.Slug.ToLower().Contains(term)
                || product.Sku.ToLower().Contains(term)
                || product.Model.ToLower().Contains(term)
                || product.ShortDescription.ToLower().Contains(term)
                || product.Description.ToLower().Contains(term));
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
            query = PublicProductTypes.Contains(value)
                ? query.Where(product => product.ProductType == value)
                : query.Where(product => false);
        }

        if (!string.IsNullOrWhiteSpace(condition))
        {
            var value = condition.Trim();
            query = PublicProductConditions.Contains(value)
                ? query.Where(product => product.Condition == value)
                : query.Where(product => false);
        }

        if (!string.IsNullOrWhiteSpace(stockStatus))
        {
            var value = stockStatus.Trim();
            query = PublicStockStatuses.Contains(value)
                ? query.Where(product => product.StockStatus == value)
                : query.Where(product => false);
        }

        return query;
    }

    private static IQueryable<Product> ApplyPublicProductOrdering(IQueryable<Product> query, string? ordering) => (ordering ?? string.Empty) switch
    {
        "name" => query.OrderBy(product => product.Name),
        "-name" => query.OrderByDescending(product => product.Name),
        "price" => query.OrderBy(product => product.Price),
        "-price" => query.OrderByDescending(product => product.Price),
        _ => query.OrderByDescending(product => product.IsFeatured).ThenBy(product => product.Name).ThenBy(product => product.Id)
    };

    private static IQueryable<Product> ApplyPublicProductFilters(IQueryable<Product> query) => query
        .Where(product => product.IsPublished)
        .Where(product => product.Category.IsActive)
        .Where(product => product.Brand == null || product.Brand.IsActive);

    private static IQueryable<Product> PublicProductReadQuery(IQueryable<Product> products) => products
        .AsNoTracking()
        .Include(product => product.Category)
        .Include(product => product.Brand)
        .Include(product => product.Images)
        .Include(product => product.Specs);

    private static IQueryable<Promotion> PublicPromotionReadQuery(IQueryable<Promotion> promotions) => promotions
        .AsNoTracking()
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Category)
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Brand)
        .Include(promotion => promotion.Product).ThenInclude(product => product!.Images);

    private static string Clean(string? value) => value?.Trim() ?? string.Empty;
}
