using System.ComponentModel.DataAnnotations;
using System.Security.Claims;
using JemNexus.Api.Data;
using JemNexus.Api.Dtos;
using JemNexus.Api.Models;
using JemNexus.Api.Utils;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static class CommercialWriteEndpoints
{
    private const string CommercialWritePolicy = "RequireCommercialWrite";
    private static readonly ISet<string> ProductTypeValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { ProductTypes.Machinery, ProductTypes.SparePart, ProductTypes.Service };
    private static readonly ISet<string> ProductConditionValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { ProductConditions.New, ProductConditions.Used, ProductConditions.Refurbished, ProductConditions.NotApplicable };
    private static readonly ISet<string> StockStatusValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { StockStatuses.Available, StockStatuses.OnRequest, StockStatuses.Sold, StockStatuses.Reserved };
    private static readonly ISet<string> PriceCurrencyValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { ProductPriceCurrencies.Clp, ProductPriceCurrencies.Usd };
    private static readonly ISet<string> PriceTaxModeValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { ProductPriceTaxModes.PlusVat, ProductPriceTaxModes.VatIncluded };
    private static readonly ISet<string> QuoteStatusValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { QuoteStatuses.New, QuoteStatuses.Contacted, QuoteStatuses.Quoted, QuoteStatuses.Closed, QuoteStatuses.Discarded };
    private static readonly ISet<string> HomeSectionValues = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { HomeSections.MachineryPromotions, HomeSections.SparePartsOffers, HomeSections.RepairServices };

    public static IEndpointRouteBuilder MapCommercialWriteEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api")
            .RequireAuthorization(CommercialWritePolicy)
            .WithTags("Commercial write");

        group.MapPost("/categories", CreateCategoryAsync).WithName("CommercialCategoriesCreate").WithOpenApi();
        group.MapMethods("/categories/{id:int}", ["PUT", "PATCH"], UpdateCategoryAsync).WithName("CommercialCategoriesUpdate");
        group.MapDelete("/categories/{id:int}", DeleteCategoryAsync).WithName("CommercialCategoriesDelete").WithOpenApi();

        group.MapPost("/brands", CreateBrandAsync).WithName("CommercialBrandsCreate").WithOpenApi();
        group.MapMethods("/brands/{id:int}", ["PUT", "PATCH"], UpdateBrandAsync).WithName("CommercialBrandsUpdate");
        group.MapDelete("/brands/{id:int}", DeleteBrandAsync).WithName("CommercialBrandsDelete").WithOpenApi();

        group.MapPost("/suppliers", CreateSupplierAsync).WithName("CommercialSuppliersCreate").WithOpenApi();
        group.MapMethods("/suppliers/{id:int}", ["PUT", "PATCH"], UpdateSupplierAsync).WithName("CommercialSuppliersUpdate");
        group.MapDelete("/suppliers/{id:int}", DeleteSupplierAsync).WithName("CommercialSuppliersDelete").WithOpenApi();

        group.MapPost("/promotions", CreatePromotionAsync).WithName("CommercialPromotionsCreate").WithOpenApi();
        group.MapMethods("/promotions/{id:int}", ["PUT", "PATCH"], UpdatePromotionAsync).WithName("CommercialPromotionsUpdate");
        group.MapDelete("/promotions/{id:int}", DeletePromotionAsync).WithName("CommercialPromotionsDelete").WithOpenApi();

        group.MapPost("/products", CreateProductAsync).WithName("CommercialProductsCreate").WithOpenApi();
        group.MapMethods("/products/{idOrSlug}", ["PUT", "PATCH"], UpdateProductAsync).WithName("CommercialProductsUpdate");
        group.MapDelete("/products/{idOrSlug}", DeleteProductAsync).WithName("CommercialProductsDelete").WithOpenApi();

        group.MapPost("/product-specs", CreateProductSpecAsync).WithName("CommercialProductSpecsCreate").WithOpenApi();
        group.MapMethods("/product-specs/{id:int}", ["PUT", "PATCH"], UpdateProductSpecAsync).WithName("CommercialProductSpecsUpdate");
        group.MapDelete("/product-specs/{id:int}", DeleteProductSpecAsync).WithName("CommercialProductSpecsDelete").WithOpenApi();

        group.MapPatch("/quote-requests/{id:int}", UpdateQuoteRequestAsync).WithName("CommercialQuoteRequestsUpdate").WithOpenApi();

        group.MapPost("/home-section-items", CreateHomeSectionItemAsync).WithName("CommercialHomeSectionItemsCreate").WithOpenApi();
        group.MapMethods("/home-section-items/{id:int}", ["PUT", "PATCH"], UpdateHomeSectionItemAsync).WithName("CommercialHomeSectionItemsUpdate");
        group.MapDelete("/home-section-items/{id:int}", DeleteHomeSectionItemAsync).WithName("CommercialHomeSectionItemsDelete").WithOpenApi();

        return app;
    }

    private static async Task<IResult> CreateCategoryAsync(CategoryWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Name));
        if (validation is not null) return validation;
        var categoryValidation = await ValidateCategoryAsync(request, dbContext, currentCategoryId: null, isCreate: true, cancellationToken);
        if (categoryValidation is not null) return categoryValidation;

        var category = new Category();
        await ApplyCategoryAsync(category, request, dbContext, user, isCreate: true, cancellationToken);
        dbContext.Categories.Add(category);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/categories/{category.Id}", CategoryReadDto.FromCategory(category));
    }

    private static async Task<IResult> UpdateCategoryAsync(int id, CategoryWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var category = await dbContext.Categories.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (category is null) return Results.NotFound(new { detail = "category not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        var categoryValidation = await ValidateCategoryAsync(request, dbContext, currentCategoryId: id, isCreate: false, cancellationToken);
        if (categoryValidation is not null) return categoryValidation;
        await ApplyCategoryAsync(category, request, dbContext, user, isCreate: false, cancellationToken);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(CategoryReadDto.FromCategory(category));
    }

    private static async Task<IResult> DeleteCategoryAsync(int id, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var category = await dbContext.Categories.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (category is null) return Results.NotFound(new { detail = "category not found." });
        if (await dbContext.Products.AnyAsync(product => product.CategoryId == id, cancellationToken))
            return Results.BadRequest(new { detail = "No se puede borrar porque tiene productos asociados. Puedes inactivarla o mover los productos primero." });
        if (await dbContext.Categories.AnyAsync(candidate => candidate.ParentId == id, cancellationToken))
            return Results.BadRequest(new { detail = "No se puede borrar porque tiene subcategorías. Elimina o mueve sus subcategorías primero." });

        dbContext.Categories.Remove(category);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static async Task ApplyCategoryAsync(Category category, CategoryWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, bool isCreate, CancellationToken cancellationToken)
    {
        var name = Clean(request.Name);
        if (!string.IsNullOrWhiteSpace(name)) category.Name = name;
        if (request.Slug is not null || (isCreate && string.IsNullOrWhiteSpace(category.Slug))) category.Slug = await UniqueSlugAsync(dbContext.Categories, Clean(request.Slug) ?? category.Name, category.Id, cancellationToken);
        if (request.ParentId.HasValue || request.Parent.HasValue) category.ParentId = request.ParentId ?? request.Parent;
        if (request.ProductType is not null) category.ProductType = request.ProductType.Trim();
        if ((isCreate || request.ParentId.HasValue || request.Parent.HasValue) && category.ParentId.HasValue)
        {
            var parentProductType = await dbContext.Categories
                .AsNoTracking()
                .Where(parent => parent.Id == category.ParentId.Value)
                .Select(parent => parent.ProductType)
                .FirstOrDefaultAsync(cancellationToken);
            if (!string.IsNullOrWhiteSpace(parentProductType)) category.ProductType = parentProductType;
        }
        if (request.Description is not null) category.Description = request.Description.Trim();
        if (request.IsActive.HasValue) category.IsActive = request.IsActive.Value;
        if (request.Order.HasValue) category.Order = request.Order.Value;
        SetAudit(category, user, isCreate);
    }

    private static async Task<IResult> CreateBrandAsync(BrandWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Name));
        if (validation is not null) return validation;
        var brand = new Brand();
        await ApplyBrandAsync(brand, request, dbContext, user, isCreate: true, cancellationToken);
        dbContext.Brands.Add(brand);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/brands/{brand.Id}", BrandReadDto.FromBrand(brand));
    }

    private static async Task<IResult> UpdateBrandAsync(int id, BrandWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var brand = await dbContext.Brands.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (brand is null) return Results.NotFound(new { detail = "brand not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        await ApplyBrandAsync(brand, request, dbContext, user, isCreate: false, cancellationToken);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(BrandReadDto.FromBrand(brand));
    }

    private static async Task<IResult> DeleteBrandAsync(int id, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var brand = await dbContext.Brands.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (brand is null) return Results.NotFound(new { detail = "brand not found." });
        brand.IsActive = false;
        SetUpdatedBy(brand, user);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static async Task ApplyBrandAsync(Brand brand, BrandWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, bool isCreate, CancellationToken cancellationToken)
    {
        var name = Clean(request.Name);
        if (!string.IsNullOrWhiteSpace(name)) brand.Name = name;
        if (request.Slug is not null || (isCreate && string.IsNullOrWhiteSpace(brand.Slug))) brand.Slug = await UniqueSlugAsync(dbContext.Brands, Clean(request.Slug) ?? brand.Name, brand.Id, cancellationToken);
        if (request.Logo is not null) brand.Logo = Clean(request.Logo);
        if (request.Description is not null) brand.Description = request.Description.Trim();
        if (request.IsActive.HasValue) brand.IsActive = request.IsActive.Value;
        SetAudit(brand, user, isCreate);
    }

    private static async Task<IResult> CreateSupplierAsync(SupplierWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Name));
        if (validation is not null) return validation;
        var supplier = new Supplier();
        ApplySupplier(supplier, request, user, isCreate: true);
        dbContext.Suppliers.Add(supplier);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/suppliers/{supplier.Id}", SupplierReadDto.FromSupplier(supplier));
    }

    private static async Task<IResult> UpdateSupplierAsync(int id, SupplierWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var supplier = await dbContext.Suppliers.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (supplier is null) return Results.NotFound(new { detail = "supplier not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        ApplySupplier(supplier, request, user, isCreate: false);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(SupplierReadDto.FromSupplier(supplier));
    }

    private static async Task<IResult> DeleteSupplierAsync(int id, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var supplier = await dbContext.Suppliers.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (supplier is null) return Results.NotFound(new { detail = "supplier not found." });
        supplier.IsActive = false;
        SetUpdatedBy(supplier, user);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static void ApplySupplier(Supplier supplier, SupplierWriteDto request, ClaimsPrincipal user, bool isCreate)
    {
        var name = Clean(request.Name);
        if (!string.IsNullOrWhiteSpace(name)) supplier.Name = name;
        if (request.ContactName is not null) supplier.ContactName = request.ContactName.Trim();
        if (request.Phone is not null) supplier.Phone = request.Phone.Trim();
        if (request.Email is not null) supplier.Email = request.Email.Trim();
        if (request.Notes is not null) supplier.Notes = request.Notes.Trim();
        if (request.IsActive.HasValue) supplier.IsActive = request.IsActive.Value;
        SetAudit(supplier, user, isCreate);
    }

    private static async Task<IResult> CreatePromotionAsync(PromotionWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Title));
        if (validation is not null) return validation;
        var relation = await ValidateOptionalProductAsync(request.ProductId ?? request.Product, dbContext, cancellationToken);
        if (relation is not null) return relation;
        var promotion = new Promotion();
        ApplyPromotion(promotion, request, user, isCreate: true);
        dbContext.Promotions.Add(promotion);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/promotions/{promotion.Id}", await PromotionDetailAsync(dbContext, promotion.Id, cancellationToken));
    }

    private static async Task<IResult> UpdatePromotionAsync(int id, PromotionWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var promotion = await dbContext.Promotions.Include(item => item.Product).ThenInclude(product => product!.Category).Include(item => item.Product).ThenInclude(product => product!.Brand).FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (promotion is null) return Results.NotFound(new { detail = "promotion not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        if (request.ProductId.HasValue || request.Product.HasValue)
        {
            var relation = await ValidateOptionalProductAsync(request.ProductId ?? request.Product, dbContext, cancellationToken);
            if (relation is not null) return relation;
        }
        ApplyPromotion(promotion, request, user, isCreate: false);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(await PromotionDetailAsync(dbContext, promotion.Id, cancellationToken));
    }

    private static async Task<IResult> DeletePromotionAsync(int id, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var promotion = await dbContext.Promotions.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (promotion is null) return Results.NotFound(new { detail = "promotion not found." });
        promotion.IsActive = false;
        SetUpdatedBy(promotion, user);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static void ApplyPromotion(Promotion promotion, PromotionWriteDto request, ClaimsPrincipal user, bool isCreate)
    {
        var title = Clean(request.Title);
        if (!string.IsNullOrWhiteSpace(title)) promotion.Title = title;
        if (request.Subtitle is not null) promotion.Subtitle = request.Subtitle.Trim();
        if (request.ProductId.HasValue || request.Product.HasValue) promotion.ProductId = request.ProductId ?? request.Product;
        if (request.Image is not null) promotion.Image = Clean(request.Image);
        if (request.ButtonText is not null) promotion.ButtonText = request.ButtonText.Trim();
        if (request.ButtonUrl is not null) promotion.ButtonUrl = request.ButtonUrl.Trim();
        if (request.IsActive.HasValue) promotion.IsActive = request.IsActive.Value;
        if (request.Order.HasValue) promotion.Order = request.Order.Value;
        if (request.StartsAt.HasValue) promotion.StartsAt = request.StartsAt;
        if (request.EndsAt.HasValue) promotion.EndsAt = request.EndsAt;
        SetAudit(promotion, user, isCreate);
    }

    private static async Task<IResult> CreateProductAsync(ProductWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Name));
        if (validation is not null) return validation;
        var relation = await ValidateProductRelationsAsync(request, dbContext, requireCategory: true, cancellationToken);
        if (relation is not null) return relation;
        var valueValidation = ValidateProductValues(request);
        if (valueValidation is not null) return valueValidation;
        var product = new Product();
        await ApplyProductAsync(product, request, dbContext, user, isCreate: true, cancellationToken);
        dbContext.Products.Add(product);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/products/{product.Id}", await ProductDetailAsync(dbContext, product.Id, cancellationToken));
    }

    private static async Task<IResult> UpdateProductAsync(string idOrSlug, ProductWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var product = await ProductQuery(dbContext.Products).FirstOrDefaultAsync(candidate => candidate.Id.ToString() == idOrSlug || candidate.Slug == idOrSlug, cancellationToken);
        if (product is null) return Results.NotFound(new { detail = "product not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        var relation = await ValidateProductRelationsAsync(request, dbContext, requireCategory: false, cancellationToken);
        if (relation is not null) return relation;
        var valueValidation = ValidateProductValues(request);
        if (valueValidation is not null) return valueValidation;
        var finalRelation = await ValidateProductCategoryTypeAsync(
            request.CategoryId ?? request.Category ?? product.CategoryId,
            request.ProductType ?? product.ProductType,
            dbContext,
            cancellationToken);
        if (finalRelation is not null) return finalRelation;
        await ApplyProductAsync(product, request, dbContext, user, isCreate: false, cancellationToken);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(await ProductDetailAsync(dbContext, product.Id, cancellationToken));
    }

    private const string ProductDeleteBlockedByQuotesMessage = "No se puede eliminar este producto porque tiene cotizaciones asociadas. Puedes despublicarlo o inactivarlo.";

    private static async Task<IResult> DeleteProductAsync(string idOrSlug, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var product = await dbContext.Products.FirstOrDefaultAsync(candidate => candidate.Id.ToString() == idOrSlug || candidate.Slug == idOrSlug, cancellationToken);
        if (product is null) return Results.NotFound(new { detail = "product not found." });

        var hasQuoteRequests = await dbContext.QuoteRequests.AnyAsync(quote => quote.ProductId == product.Id, cancellationToken);
        if (hasQuoteRequests) return Results.Conflict(new { detail = ProductDeleteBlockedByQuotesMessage });

        if (dbContext.Database.IsInMemory())
        {
            await DeleteProductWithTechnicalRelationsAsync(dbContext, product, cancellationToken);
            return Results.NoContent();
        }

        await using var transaction = await dbContext.Database.BeginTransactionAsync(cancellationToken);
        await DeleteProductWithTechnicalRelationsAsync(dbContext, product, cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return Results.NoContent();
    }

    private static async Task DeleteProductWithTechnicalRelationsAsync(JemNexusDbContext dbContext, Product product, CancellationToken cancellationToken)
    {
        if (dbContext.Database.IsInMemory())
        {
            dbContext.ProductImages.RemoveRange(dbContext.ProductImages.Where(image => image.ProductId == product.Id));
            dbContext.ProductSpecs.RemoveRange(dbContext.ProductSpecs.Where(spec => spec.ProductId == product.Id));
            dbContext.HomeSectionItems.RemoveRange(dbContext.HomeSectionItems.Where(item => item.ProductId == product.Id));

            foreach (var promotion in dbContext.Promotions.Where(promotion => promotion.ProductId == product.Id))
            {
                promotion.ProductId = null;
            }
        }
        else
        {
            await dbContext.ProductImages.Where(image => image.ProductId == product.Id).ExecuteDeleteAsync(cancellationToken);
            await dbContext.ProductSpecs.Where(spec => spec.ProductId == product.Id).ExecuteDeleteAsync(cancellationToken);
            await dbContext.HomeSectionItems.Where(item => item.ProductId == product.Id).ExecuteDeleteAsync(cancellationToken);
            await dbContext.Promotions.Where(promotion => promotion.ProductId == product.Id).ExecuteUpdateAsync(
                setters => setters.SetProperty(promotion => promotion.ProductId, (int?)null),
                cancellationToken);
        }

        dbContext.Products.Remove(product);
        await dbContext.SaveChangesAsync(cancellationToken);
    }

    private static async Task ApplyProductAsync(Product product, ProductWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, bool isCreate, CancellationToken cancellationToken)
    {
        var name = Clean(request.Name);
        if (!string.IsNullOrWhiteSpace(name)) product.Name = name;
        if (request.Slug is not null || (isCreate && string.IsNullOrWhiteSpace(product.Slug))) product.Slug = await UniqueSlugAsync(dbContext.Products, Clean(request.Slug) ?? product.Name, product.Id, cancellationToken);
        if (request.CategoryId.HasValue || request.Category.HasValue) product.CategoryId = (request.CategoryId ?? request.Category)!.Value;
        if (isCreate || request.CategoryId.HasValue || request.Category.HasValue || request.ProductType is null)
        {
            var categoryProductType = await dbContext.Categories
                .AsNoTracking()
                .Where(category => category.Id == product.CategoryId)
                .Select(category => category.ProductType)
                .FirstOrDefaultAsync(cancellationToken);
            if (!string.IsNullOrWhiteSpace(categoryProductType)) product.ProductType = categoryProductType;
        }
        if (request.BrandId.HasValue || request.Brand.HasValue) product.BrandId = request.BrandId ?? request.Brand;
        if (request.SupplierId.HasValue || request.Supplier.HasValue) product.SupplierId = request.SupplierId ?? request.Supplier;
        if (request.ProductType is not null) product.ProductType = request.ProductType.Trim();
        if (request.Condition is not null) product.Condition = request.Condition.Trim();
        if (request.ShortDescription is not null) product.ShortDescription = request.ShortDescription.Trim();
        if (request.Description is not null) product.Description = request.Description.Trim();
        if (request.Model is not null) product.Model = request.Model.Trim();
        if (request.Sku is not null) product.Sku = request.Sku.Trim();
        if (request.Year.HasValue) product.Year = request.Year;
        if (request.HoursMeter.HasValue) product.HoursMeter = request.HoursMeter;
        if (request.Price.HasValue) product.Price = request.Price;
        if (request.PriceCurrency is not null) product.PriceCurrency = request.PriceCurrency.Trim().ToUpperInvariant();
        if (request.PriceTaxMode is not null) product.PriceTaxMode = request.PriceTaxMode.Trim().ToLowerInvariant();
        if (request.PriceVisible.HasValue) product.PriceVisible = request.PriceVisible.Value;
        if (request.StockStatus is not null) product.StockStatus = request.StockStatus.Trim();
        if (request.IsFeatured.HasValue) product.IsFeatured = request.IsFeatured.Value;
        if (request.IsPublished.HasValue) product.IsPublished = request.IsPublished.Value;
        SetAudit(product, user, isCreate);
    }

    private static async Task<IResult> CreateProductSpecAsync(ProductSpecWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateRequest(request, nameof(request.Value));
        if (validation is not null) return validation;
        var productId = request.ProductId ?? request.Product;
        if (!productId.HasValue || !await dbContext.Products.AnyAsync(product => product.Id == productId.Value, cancellationToken)) return Results.BadRequest(new { detail = "product does not exist." });
        var key = Clean(request.Key) ?? Clean(request.Name);
        if (string.IsNullOrWhiteSpace(key)) return Results.BadRequest(new { detail = "name is required." });
        var spec = new ProductSpec { ProductId = productId.Value };
        ApplyProductSpec(spec, request, user, isCreate: true);
        dbContext.ProductSpecs.Add(spec);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/product-specs/{spec.Id}", ProductSpecReadDto.FromSpec(spec));
    }

    private static async Task<IResult> UpdateProductSpecAsync(int id, ProductSpecWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var spec = await dbContext.ProductSpecs.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (spec is null) return Results.NotFound(new { detail = "product spec not found." });
        var validation = ValidateRequest(request);
        if (validation is not null) return validation;
        if ((request.ProductId.HasValue || request.Product.HasValue) && !await dbContext.Products.AnyAsync(product => product.Id == (request.ProductId ?? request.Product)!.Value, cancellationToken)) return Results.BadRequest(new { detail = "product does not exist." });
        ApplyProductSpec(spec, request, user, isCreate: false);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(ProductSpecReadDto.FromSpec(spec));
    }

    private static async Task<IResult> DeleteProductSpecAsync(int id, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var spec = await dbContext.ProductSpecs.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (spec is null) return Results.NotFound(new { detail = "product spec not found." });
        dbContext.ProductSpecs.Remove(spec);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static void ApplyProductSpec(ProductSpec spec, ProductSpecWriteDto request, ClaimsPrincipal user, bool isCreate)
    {
        if (request.ProductId.HasValue || request.Product.HasValue) spec.ProductId = (request.ProductId ?? request.Product)!.Value;
        var key = Clean(request.Key) ?? Clean(request.Name);
        if (!string.IsNullOrWhiteSpace(key)) spec.Key = key;
        if (request.Value is not null) spec.Value = request.Value.Trim();
        if (request.Unit is not null) spec.Unit = request.Unit.Trim();
        if (request.Order.HasValue) spec.Order = request.Order.Value;
        SetAudit(spec, user, isCreate);
    }

    private static async Task<IResult> UpdateQuoteRequestAsync(int id, QuoteRequestWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var quote = await dbContext.QuoteRequests.Include(item => item.Product).FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (quote is null) return Results.NotFound(new { detail = "quote request not found." });
        if (request.Status is not null)
        {
            var status = request.Status.Trim();
            if (!QuoteStatusValues.Contains(status)) return Results.BadRequest(new { detail = "invalid quote status." });
            quote.Status = status;
            var now = DateTimeOffset.UtcNow;
            if (status == QuoteStatuses.Contacted && quote.ContactedAt is null) quote.ContactedAt = now;
            if (status == QuoteStatuses.Quoted && quote.QuotedAt is null) quote.QuotedAt = now;
            if ((status == QuoteStatuses.Closed || status == QuoteStatuses.Discarded) && quote.ClosedAt is null) quote.ClosedAt = now;
        }
        if (request.InternalNotes is not null) quote.InternalNotes = request.InternalNotes.Trim();
        if (request.SellerResponse is not null) quote.SellerResponse = request.SellerResponse.Trim();
        SetUpdatedBy(quote, user);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(QuoteRequestReadDto.FromQuoteRequest(quote));
    }

    private static async Task<IResult> CreateHomeSectionItemAsync(HomeSectionItemWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var validation = ValidateHomeSectionRequest(request, requireProduct: true);
        if (validation is not null) return validation;
        if (!await dbContext.Products.AnyAsync(product => product.Id == (request.ProductId ?? request.Product)!.Value, cancellationToken)) return Results.BadRequest(new { detail = "product does not exist." });
        var item = new HomeSectionItem();
        ApplyHomeSectionItem(item, request, user, isCreate: true);
        dbContext.HomeSectionItems.Add(item);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Created($"/api/home-section-items/{item.Id}", await HomeSectionDetailAsync(dbContext, item.Id, cancellationToken));
    }

    private static async Task<IResult> UpdateHomeSectionItemAsync(int id, HomeSectionItemWriteDto request, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var item = await dbContext.HomeSectionItems.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (item is null) return Results.NotFound(new { detail = "home section item not found." });
        var validation = ValidateHomeSectionRequest(request, requireProduct: false);
        if (validation is not null) return validation;
        if ((request.ProductId.HasValue || request.Product.HasValue) && !await dbContext.Products.AnyAsync(product => product.Id == (request.ProductId ?? request.Product)!.Value, cancellationToken)) return Results.BadRequest(new { detail = "product does not exist." });
        ApplyHomeSectionItem(item, request, user, isCreate: false);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.Ok(await HomeSectionDetailAsync(dbContext, item.Id, cancellationToken));
    }

    private static async Task<IResult> DeleteHomeSectionItemAsync(int id, JemNexusDbContext dbContext, ClaimsPrincipal user, CancellationToken cancellationToken)
    {
        var item = await dbContext.HomeSectionItems.FirstOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);
        if (item is null) return Results.NotFound(new { detail = "home section item not found." });
        item.IsActive = false;
        SetUpdatedBy(item, user);
        await dbContext.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    }

    private static void ApplyHomeSectionItem(HomeSectionItem item, HomeSectionItemWriteDto request, ClaimsPrincipal user, bool isCreate)
    {
        if (request.Section is not null) item.Section = request.Section.Trim();
        if (request.Position.HasValue) item.Position = request.Position.Value;
        if (request.ProductId.HasValue || request.Product.HasValue) item.ProductId = (request.ProductId ?? request.Product)!.Value;
        if (request.IsActive.HasValue) item.IsActive = request.IsActive.Value;
        SetAudit(item, user, isCreate);
    }

    private static IResult? ValidateRequest<T>(T request, params string[] requiredMembers)
    {
        var results = new List<ValidationResult>();
        if (!Validator.TryValidateObject(request!, new ValidationContext(request!), results, validateAllProperties: true))
        {
            return Results.BadRequest(new { detail = string.Join(" ", results.Select(result => result.ErrorMessage)) });
        }
        foreach (var member in requiredMembers)
        {
            var property = typeof(T).GetProperty(member);
            if (property?.GetValue(request) is not string value || string.IsNullOrWhiteSpace(value)) return Results.BadRequest(new { detail = $"{member.ToLowerInvariant()} is required." });
        }
        return null;
    }

    private static async Task<IResult?> ValidateCategoryAsync(CategoryWriteDto request, JemNexusDbContext dbContext, int? currentCategoryId, bool isCreate, CancellationToken cancellationToken)
    {
        var productType = request.ProductType?.Trim();
        if (!isCreate && string.IsNullOrWhiteSpace(productType) && currentCategoryId.HasValue)
        {
            productType = await dbContext.Categories
                .AsNoTracking()
                .Where(category => category.Id == currentCategoryId.Value)
                .Select(category => category.ProductType)
                .FirstOrDefaultAsync(cancellationToken);
        }
        var parentId = request.ParentId ?? request.Parent;
        if (parentId.HasValue && string.IsNullOrWhiteSpace(productType))
        {
            productType = await dbContext.Categories
                .AsNoTracking()
                .Where(category => category.Id == parentId.Value)
                .Select(category => category.ProductType)
                .FirstOrDefaultAsync(cancellationToken);
        }
        if (isCreate && string.IsNullOrWhiteSpace(productType)) productType = ProductTypes.Machinery;
        if (!string.IsNullOrWhiteSpace(productType) && !ProductTypeValues.Contains(productType)) return Results.BadRequest(new { detail = "invalid product_type." });

        if (!parentId.HasValue) return null;
        if (currentCategoryId.HasValue && parentId.Value == currentCategoryId.Value) return Results.BadRequest(new { detail = "category cannot be its own parent." });

        var parent = await dbContext.Categories.AsNoTracking().FirstOrDefaultAsync(category => category.Id == parentId.Value, cancellationToken);
        if (parent is null) return Results.BadRequest(new { detail = "parent category does not exist." });
        if (parent.ParentId.HasValue) return Results.BadRequest(new { detail = "category hierarchy is limited to two levels." });
        if (currentCategoryId.HasValue && await dbContext.Categories.AnyAsync(child => child.ParentId == currentCategoryId.Value, cancellationToken))
            return Results.BadRequest(new { detail = "category hierarchy is limited to two levels. Move or delete subcategories before moving this category under another parent." });
        if (!parent.IsActive) return Results.BadRequest(new { detail = "parent category must be active." });
        if (!string.IsNullOrWhiteSpace(productType) && !string.Equals(parent.ProductType, productType, StringComparison.OrdinalIgnoreCase))
            return Results.BadRequest(new { detail = "parent category must belong to the same product_type." });
        return null;
    }

    private static IResult? ValidateProductValues(ProductWriteDto request)
    {
        if (request.ProductType is not null && !ProductTypeValues.Contains(request.ProductType.Trim())) return Results.BadRequest(new { detail = "invalid product_type." });
        if (request.Condition is not null && !ProductConditionValues.Contains(request.Condition.Trim())) return Results.BadRequest(new { detail = "invalid condition." });
        if (request.StockStatus is not null && !StockStatusValues.Contains(request.StockStatus.Trim())) return Results.BadRequest(new { detail = "invalid stock_status." });
        if (request.PriceCurrency is not null && !PriceCurrencyValues.Contains(request.PriceCurrency.Trim())) return Results.BadRequest(new { detail = "invalid price_currency. Use CLP or USD." });
        if (request.PriceTaxMode is not null && !PriceTaxModeValues.Contains(request.PriceTaxMode.Trim())) return Results.BadRequest(new { detail = "invalid price_tax_mode. Use plus_vat or vat_included." });
        return null;
    }

    private static IResult? ValidateHomeSectionRequest(HomeSectionItemWriteDto request, bool requireProduct)
    {
        var validation = requireProduct
            ? ValidateRequest(request, nameof(request.Section))
            : ValidateRequest(request);
        if (validation is not null) return validation;
        if (request.Section is not null && !HomeSectionValues.Contains(request.Section.Trim())) return Results.BadRequest(new { detail = "invalid section." });
        if (requireProduct && !(request.ProductId.HasValue || request.Product.HasValue)) return Results.BadRequest(new { detail = "product is required." });
        return null;
    }

    private static async Task<IResult?> ValidateOptionalProductAsync(int? productId, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        if (productId.HasValue && !await dbContext.Products.AnyAsync(product => product.Id == productId.Value, cancellationToken)) return Results.BadRequest(new { detail = "product does not exist." });
        return null;
    }

    private static async Task<IResult?> ValidateProductRelationsAsync(ProductWriteDto request, JemNexusDbContext dbContext, bool requireCategory, CancellationToken cancellationToken)
    {
        var categoryId = request.CategoryId ?? request.Category;
        if (requireCategory && !categoryId.HasValue) return Results.BadRequest(new { detail = "category is required." });
        if (categoryId.HasValue)
        {
            var categoryValidation = await ValidateProductCategoryTypeAsync(categoryId.Value, request.ProductType, dbContext, cancellationToken);
            if (categoryValidation is not null) return categoryValidation;
        }
        var brandId = request.BrandId ?? request.Brand;
        if (brandId.HasValue && !await dbContext.Brands.AnyAsync(brand => brand.Id == brandId.Value, cancellationToken)) return Results.BadRequest(new { detail = "brand does not exist." });
        var supplierId = request.SupplierId ?? request.Supplier;
        if (supplierId.HasValue && !await dbContext.Suppliers.AnyAsync(supplier => supplier.Id == supplierId.Value, cancellationToken)) return Results.BadRequest(new { detail = "supplier does not exist." });
        return null;
    }

    private static async Task<IResult?> ValidateProductCategoryTypeAsync(int categoryId, string? productType, JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var category = await dbContext.Categories.AsNoTracking().FirstOrDefaultAsync(category => category.Id == categoryId, cancellationToken);
        if (category is null) return Results.BadRequest(new { detail = "category does not exist." });
        if (!category.IsActive) return Results.BadRequest(new { detail = "category must be active." });
        var normalizedProductType = productType?.Trim();
        if (!string.IsNullOrWhiteSpace(normalizedProductType) && !ProductTypeValues.Contains(normalizedProductType))
            return Results.BadRequest(new { detail = "invalid product_type." });
        if (!string.IsNullOrWhiteSpace(normalizedProductType) && !string.Equals(category.ProductType, normalizedProductType, StringComparison.OrdinalIgnoreCase))
            return Results.BadRequest(new { detail = "category must belong to the selected product_type." });
        return null;
    }

    private static async Task<string> UniqueSlugAsync<T>(IQueryable<T> set, string source, int currentId, CancellationToken cancellationToken) where T : class
    {
        var baseSlug = SlugHelper.GenerateSlug(source);
        var slug = baseSlug;
        var suffix = 2;
        while (await set.AnyAsync(entity => EF.Property<string>(entity, "Slug") == slug && EF.Property<int>(entity, "Id") != currentId, cancellationToken))
        {
            slug = $"{baseSlug}-{suffix}";
            suffix++;
        }
        return slug;
    }

    private static async Task<ProductDetailReadDto> ProductDetailAsync(JemNexusDbContext dbContext, int id, CancellationToken cancellationToken)
    {
        var product = await ProductQuery(dbContext.Products).FirstAsync(candidate => candidate.Id == id, cancellationToken);
        return ProductDetailReadDto.FromProduct(product);
    }

    private static IQueryable<Product> ProductQuery(DbSet<Product> products) => products
        .Include(product => product.Category)
        .Include(product => product.Brand)
        .Include(product => product.Supplier)
        .Include(product => product.Images)
        .Include(product => product.Specs);

    private static async Task<PromotionReadDto> PromotionDetailAsync(JemNexusDbContext dbContext, int id, CancellationToken cancellationToken)
    {
        var promotion = await dbContext.Promotions
            .Include(candidate => candidate.Product)
            .ThenInclude(product => product!.Category)
            .Include(candidate => candidate.Product)
            .ThenInclude(product => product!.Brand)
            .FirstAsync(candidate => candidate.Id == id, cancellationToken);
        return PromotionReadDto.FromPromotion(promotion);
    }

    private static async Task<HomeSectionItemReadDto> HomeSectionDetailAsync(JemNexusDbContext dbContext, int id, CancellationToken cancellationToken)
    {
        var item = await dbContext.HomeSectionItems.Include(candidate => candidate.Product).ThenInclude(product => product.Category).Include(candidate => candidate.Product).ThenInclude(product => product.Brand).FirstAsync(candidate => candidate.Id == id, cancellationToken);
        return HomeSectionItemReadDto.FromHomeSectionItem(item);
    }

    private static string? Clean(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    private static int? CurrentUserId(ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? user.FindFirstValue("sub");
        return int.TryParse(raw, out var id) ? id : null;
    }

    private static void SetAudit(object entity, ClaimsPrincipal user, bool isCreate)
    {
        if (isCreate) SetCreatedBy(entity, user);
        SetUpdatedBy(entity, user);
    }

    private static void SetCreatedBy(object entity, ClaimsPrincipal user)
    {
        var id = CurrentUserId(user);
        if (id is null) return;
        entity.GetType().GetProperty("CreatedById")?.SetValue(entity, id.Value);
    }

    private static void SetUpdatedBy(object entity, ClaimsPrincipal user)
    {
        var id = CurrentUserId(user);
        if (id is null) return;
        entity.GetType().GetProperty("UpdatedById")?.SetValue(entity, id.Value);
    }
}
