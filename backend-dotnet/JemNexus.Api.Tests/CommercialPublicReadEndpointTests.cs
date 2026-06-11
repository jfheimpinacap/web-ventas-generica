using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialPublicReadEndpointTests : IDisposable
{
    private readonly CommercialWriteEndpointTests.CommercialWriteApiFactory _factory = new();

    public void Dispose() => _factory.Dispose();

    [Theory]
    [InlineData("/api/public/products/")]
    [InlineData("/api/public/categories/")]
    [InlineData("/api/public/brands/")]
    [InlineData("/api/public/promotions/")]
    [InlineData("/api/public/home-section-items/")]
    public async Task PublicReadEndpointsAllowAnonymous(string path)
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task PublicProductsFilterUnpublishedAndInactiveRelationsAndExcludeAdminFields()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var products = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?include_unpublished=true"));
        var body = products.ToString();

        Assert.Single(products.EnumerateArray());
        Assert.Equal("excavadora", products[0].GetProperty("slug").GetString());
        Assert.DoesNotContain("borrador", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("categoria-inactiva", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("created_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("updated_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("created_by", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("updated_by", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("supplier", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("password", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicProductDetailReturnsPublishedProductAndHidesUnpublishedProduct()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var published = await client.GetAsync("/api/public/products/excavadora/");
        var unpublished = await client.GetAsync("/api/public/products/borrador/");
        var payload = await ReadJsonAsync<JsonElement>(published);
        var body = payload.ToString();

        Assert.Equal(HttpStatusCode.OK, published.StatusCode);
        Assert.Equal("excavadora", payload.GetProperty("slug").GetString());
        Assert.Equal(HttpStatusCode.NotFound, unpublished.StatusCode);
        Assert.DoesNotContain("created_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("supplier", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicProductFiltersWorkWithSearchCategoryBrandAndSafeOrdering()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var bySearch = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?search=excavadora"));
        var byCategory = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?category=maquinaria"));
        var byBrand = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?brand=acme"));
        var byType = await ReadJsonAsync<JsonElement>(await client.GetAsync($"/api/public/products/?product_type={ProductTypes.Machinery}&condition={ProductConditions.Used}&stock_status={StockStatuses.Available}&ordering=price"));
        var unsafeOrdering = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?ordering=created_at"));

        Assert.Single(bySearch.EnumerateArray());
        Assert.Single(byCategory.EnumerateArray());
        Assert.Single(byBrand.EnumerateArray());
        Assert.Single(byType.EnumerateArray());
        Assert.Single(unsafeOrdering.EnumerateArray());
    }

    [Fact]
    public async Task PublicPromotionHomeSpecsAndImagesOnlyExposePublishedActiveData()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var promotions = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/promotions/"));
        var homeItems = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/home-section-items/"));
        var specs = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-specs/?product=1"));
        var hiddenSpecs = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-specs/?product=3"));
        var images = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-images/?product=1"));
        var hiddenImages = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-images/?product=3"));

        Assert.Single(promotions.EnumerateArray());
        Assert.Equal("Promo vigente", promotions[0].GetProperty("title").GetString());
        Assert.Single(homeItems.EnumerateArray());
        Assert.Single(specs.EnumerateArray());
        Assert.Empty(hiddenSpecs.EnumerateArray());
        Assert.Single(images.EnumerateArray());
        Assert.Empty(hiddenImages.EnumerateArray());
    }

    [Theory]
    [InlineData("/api/products/")]
    [InlineData("/api/categories/")]
    public async Task AdminReadEndpointsStillRequireBearerToken(string path)
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    private async Task SeedPublicCatalogDataAsync()
    {
        await _factory.SeedCommercialDataAsync();

        using var scope = _factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        if (await dbContext.Products.AnyAsync(product => product.Slug == "borrador")) return;

        var inactiveCategory = new Category { Id = 3, Name = "Categoría Inactiva", Slug = "categoria-inactiva", IsActive = false, Description = "No pública", Order = 3 };
        var inactiveBrand = new Brand { Id = 2, Name = "Marca Inactiva", Slug = "marca-inactiva", IsActive = false };
        var draftProduct = new Product { Id = 3, Name = "Borrador", Slug = "borrador", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = false };
        var inactiveCategoryProduct = new Product { Id = 4, Name = "Producto Inactivo", Slug = "producto-inactivo", Category = inactiveCategory, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };
        var inactiveBrandProduct = new Product { Id = 5, Name = "Marca Oculta", Slug = "marca-oculta", CategoryId = 1, Brand = inactiveBrand, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };

        dbContext.Categories.Add(inactiveCategory);
        dbContext.Brands.Add(inactiveBrand);
        dbContext.Products.AddRange(draftProduct, inactiveCategoryProduct, inactiveBrandProduct);
        dbContext.ProductImages.AddRange(
            new ProductImage { Id = 1, ProductId = 1, Image = "/media/excavadora.jpg", AltText = "Excavadora", IsMain = true },
            new ProductImage { Id = 2, Product = draftProduct, Image = "/media/borrador.jpg", AltText = "Borrador", IsMain = true });
        dbContext.ProductSpecs.Add(new ProductSpec { Id = 2, Product = draftProduct, Key = "Oculta", Value = "No", Unit = string.Empty });
        dbContext.Promotions.AddRange(
            new Promotion { Id = 1, Title = "Promo vigente", ProductId = 1, IsActive = true, StartsAt = DateTimeOffset.UtcNow.AddDays(-1), EndsAt = DateTimeOffset.UtcNow.AddDays(1), Order = 1 },
            new Promotion { Id = 2, Title = "Promo inactiva", ProductId = 1, IsActive = false, Order = 2 },
            new Promotion { Id = 3, Title = "Promo borrador", Product = draftProduct, IsActive = true, Order = 3 });
        dbContext.HomeSectionItems.Add(new HomeSectionItem { Id = 2, Section = HomeSections.MachineryPromotions, Product = draftProduct, Position = 2, IsActive = true });
        await dbContext.SaveChangesAsync();
    }

    private static async Task<T> ReadJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response for {typeof(T).Name}. Body: {body}");
        return payload!;
    }
}
