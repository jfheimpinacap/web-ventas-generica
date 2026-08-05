using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using JemNexus.Api.Services.ProductImages;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialWriteEndpointTests : IDisposable
{
    private const string TestPassword = "DummyPassword123!";
    private readonly CommercialWriteApiFactory _factory = new();

    public void Dispose() => _factory.Dispose();

    [Theory]
    [InlineData("POST", "/api/categories/")]
    [InlineData("PATCH", "/api/products/1/")]
    [InlineData("DELETE", "/api/brands/1/")]
    public async Task CommercialWriteEndpointsRequireBearerToken(string method, string path)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method is "POST" or "PATCH") request.Content = JsonContent.Create(new { name = "Demo", product_type = ProductTypes.Machinery });

        var response = await client.SendAsync(request);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task NonCommercialUserCannotWrite()
    {
        await _factory.SeedCommercialDataAsync();
        await _factory.SeedUnauthorizedUserAsync();
        using var client = await CreateAuthorizedClientAsync("viewer");

        var response = await client.PostAsJsonAsync("/api/categories/", new { name = "Bloqueada", product_type = ProductTypes.Machinery });

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task SellerCanCreateEditAndSoftDeleteCategoryBrandSupplierPromotion()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var category = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/categories/", new { name = "Filtros", product_type = ProductTypes.Machinery, order = 9 }));
        var categoryId = category.GetProperty("id").GetInt32();
        var categoryUpdate = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/categories/{categoryId}/", new { description = "Editada", product_type = ProductTypes.Machinery, is_active = true }));
        Assert.Equal("Editada", categoryUpdate.GetProperty("description").GetString());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/categories/{categoryId}/")).StatusCode);

        var brand = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/brands/", new { name = "Marca Nueva", is_active = true, created_by = 999 }));
        var brandId = brand.GetProperty("id").GetInt32();
        var brandUpdate = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/brands/{brandId}/", new { description = "Visible" }));
        Assert.Equal("Visible", brandUpdate.GetProperty("description").GetString());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/brands/{brandId}/")).StatusCode);

        var supplier = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/suppliers/", new { name = "Proveedor Nuevo", phone = "+569" }));
        var supplierId = supplier.GetProperty("id").GetInt32();
        var supplierUpdate = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/suppliers/{supplierId}/", new { contact_name = "Contacto" }));
        Assert.Equal("Contacto", supplierUpdate.GetProperty("contact_name").GetString());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/suppliers/{supplierId}/")).StatusCode);

        var promotion = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/promotions/", new { title = "Promo", product = 1, button_text = "Ver", is_active = true }));
        var promotionId = promotion.GetProperty("id").GetInt32();
        var promotionUpdate = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/promotions/{promotionId}/", new { subtitle = "Sub" }));
        Assert.Equal("Sub", promotionUpdate.GetProperty("subtitle").GetString());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/promotions/{promotionId}/")).StatusCode);
    }

    [Fact]
    public async Task SellerCanCreateEditAndSoftDeleteBasicProductWithValidRelations()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products/", new
        {
            name = "Producto Base",
            category = 1,
            brand = 1,
            supplier = 1,
            product_type = ProductTypes.Machinery,
            condition = ProductConditions.Used,
            stock_status = StockStatuses.Available,
            is_published = true,
            password = "ignored",
            created_by = 999
        }));

        Assert.Equal("Producto Base", created.GetProperty("name").GetString());
        Assert.False(created.TryGetProperty("created_by", out _));
        Assert.False(created.ToString().Contains("password", StringComparison.OrdinalIgnoreCase));

        var slug = created.GetProperty("slug").GetString();
        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/products/{slug}/", new { short_description = "Actualizado", is_featured = true }));
        Assert.Equal("Actualizado", updated.GetProperty("short_description").GetString());

        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/products/{slug}/")).StatusCode);
    }

    [Theory]
    [InlineData(ProductPowerSources.Diesel)]
    [InlineData(ProductPowerSources.Electric24V)]
    [InlineData(ProductPowerSources.ElectricLithium)]
    public async Task MachineryTechnicalDataSupportsAllowedPowerSourcesAndPurchaseDefaults(string powerSource)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products/", new
        {
            name = $"Equipo {powerSource}", category = 1, product_type = ProductTypes.Machinery,
            condition = ProductConditions.New, stock_status = StockStatuses.Available,
            maximum_load_capacity_kg = 2000.50m, power_source = powerSource, year = 2024
        }));

        Assert.Equal(powerSource, created.GetProperty("power_source").GetString());
        Assert.Equal(2000.50m, created.GetProperty("maximum_load_capacity_kg").GetDecimal());
        Assert.True(created.GetProperty("includes_technical_review").GetBoolean());
        Assert.True(created.GetProperty("includes_commercial_technical_advice").GetBoolean());
        Assert.True(created.GetProperty("includes_coordinated_delivery").GetBoolean());

        var slug = created.GetProperty("slug").GetString();
        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/products/{slug}/", new
        {
            maximum_load_capacity_kg = 2500m, includes_technical_review = false
        }));
        Assert.Equal(2500m, updated.GetProperty("maximum_load_capacity_kg").GetDecimal());
        Assert.False(updated.GetProperty("includes_technical_review").GetBoolean());
    }

    [Fact]
    public async Task MachineryTechnicalDataRejectsInvalidValuesAndSparePartsKeepFalseDefaults()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var invalidCapacity = await client.PostAsJsonAsync("/api/products/", new { name = "Inválido", category = 1, maximum_load_capacity_kg = 0 });
        var invalidPower = await client.PostAsJsonAsync("/api/products/", new { name = "Inválido", category = 1, power_source = "solar" });
        var invalidYear = await client.PostAsJsonAsync("/api/products/", new { name = "Inválido", category = 1, year = 1800 });
        Assert.Equal(HttpStatusCode.BadRequest, invalidCapacity.StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, invalidPower.StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, invalidYear.StatusCode);

        var spare = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products/", new
        {
            name = "Repuesto compatible", category = 2, product_type = ProductTypes.SparePart,
            condition = ProductConditions.New, stock_status = StockStatuses.Available
        }));
        Assert.False(spare.GetProperty("includes_technical_review").GetBoolean());
        Assert.False(spare.GetProperty("includes_commercial_technical_advice").GetBoolean());
        Assert.False(spare.GetProperty("includes_coordinated_delivery").GetBoolean());

        var used = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products/", new
        {
            name = "Maquinaria usada", category = 1, product_type = ProductTypes.Machinery,
            condition = ProductConditions.Used, stock_status = StockStatuses.Available,
            includes_coordinated_delivery = false
        }));
        Assert.True(used.GetProperty("includes_technical_review").GetBoolean());
        Assert.True(used.GetProperty("includes_commercial_technical_advice").GetBoolean());
        Assert.False(used.GetProperty("includes_coordinated_delivery").GetBoolean());
    }

    [Fact]
    public async Task DeleteProductWithoutQuotesPhysicallyRemovesProductAndTechnicalRelations()
    {
        await _factory.SeedCommercialDataAsync();

        using (var scope = _factory.Services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var product = await dbContext.Products.FirstAsync(product => product.Id == 2);
            dbContext.ProductImages.Add(new ProductImage { Id = 10, Product = product, Image = "products/filtro.jpg", AltText = "Filtro" });
            dbContext.ProductSpecs.Add(new ProductSpec { Id = 10, Product = product, Key = "Medida", Value = "10", Unit = "cm" });
            dbContext.Promotions.Add(new Promotion { Id = 10, Title = "Oferta filtro", Product = product, IsActive = true });
            dbContext.HomeSectionItems.Add(new HomeSectionItem { Id = 10, Section = HomeSections.SparePartsOffers, Product = product, Position = 1, IsActive = true });
            await dbContext.SaveChangesAsync();
        }

        using var client = await CreateAuthorizedClientAsync();
        var deleteResponse = await client.DeleteAsync("/api/products/filtro/");
        var listResponse = await client.GetAsync("/api/products/?include_unpublished=true");
        var listBody = await listResponse.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);
        Assert.DoesNotContain("filtro", listBody, StringComparison.OrdinalIgnoreCase);

        using var assertScope = _factory.Services.CreateScope();
        var assertContext = assertScope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.False(await assertContext.Products.AnyAsync(product => product.Id == 2));
        Assert.False(await assertContext.ProductImages.AnyAsync(image => image.ProductId == 2));
        Assert.False(await assertContext.ProductSpecs.AnyAsync(spec => spec.ProductId == 2));
        Assert.False(await assertContext.HomeSectionItems.AnyAsync(item => item.ProductId == 2));
        var promotion = await assertContext.Promotions.SingleAsync(promotion => promotion.Id == 10);
        Assert.Null(promotion.ProductId);
    }

    [Fact]
    public async Task DeleteProductWithQuotesReturnsConflictAndKeepsCommercialData()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var response = await client.DeleteAsync("/api/products/excavadora/");
        var body = await response.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.Conflict, response.StatusCode);
        Assert.Contains("No se puede eliminar este producto porque tiene cotizaciones asociadas", body);

        using var scope = _factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.True(await dbContext.Products.AnyAsync(product => product.Id == 1 && product.IsPublished));
        Assert.True(await dbContext.QuoteRequests.AnyAsync(quote => quote.Id == 1 && quote.ProductId == 1 && quote.Status == QuoteStatuses.New));
    }

    [Fact]
    public async Task ProductRejectsMissingRelationsAndInvalidEnums()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var missingCategory = await client.PostAsJsonAsync("/api/products/", new { name = "Sin relación", category = 999 });
        var invalidStatus = await client.PostAsJsonAsync("/api/products/", new { name = "Estado malo", category = 1, stock_status = "bad" });

        Assert.Equal(HttpStatusCode.BadRequest, missingCategory.StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, invalidStatus.StatusCode);
    }


    [Fact]
    public async Task SellerCanUploadUpdatePromoteOrderAndDeleteProductImages()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var initialEmpty = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=2"));
        Assert.Empty(initialEmpty.EnumerateArray());
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/product-images/?product=999")).StatusCode);

        var first = await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/product-images/", ImageForm(1, "uno.jpg", "image/jpeg", JpegBytes(), "Principal", isMain: false, order: 2)));
        Assert.True(first.GetProperty("is_main").GetBoolean());
        var firstImageUrl = first.GetProperty("image").GetString();
        Assert.StartsWith("/media/product-images/1/", firstImageUrl);
        Assert.DoesNotContain("/workspace", firstImageUrl);
        Assert.True(File.Exists(_factory.PhysicalUploadPath(firstImageUrl!)));

        var third = await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/product-images/", ImageForm(1, "tres.jpeg", "image/jpeg", JpegBytes(), "Tres", isMain: false, order: 3)));
        Assert.False(third.GetProperty("is_main").GetBoolean());

        var second = await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/product-images/", ImageForm(1, "../dos.png", "image/png", PngBytes(), "Dos", isMain: true, order: 1)));
        var firstId = first.GetProperty("id").GetInt32();
        var secondId = second.GetProperty("id").GetInt32();
        var thirdId = third.GetProperty("id").GetInt32();
        Assert.True(second.GetProperty("is_main").GetBoolean());

        var list = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=1"));
        Assert.Equal(secondId, list[0].GetProperty("id").GetInt32());
        Assert.Equal(firstId, list[1].GetProperty("id").GetInt32());
        Assert.Equal(thirdId, list[2].GetProperty("id").GetInt32());
        Assert.Single(list.EnumerateArray().Where(image => image.GetProperty("is_main").GetBoolean()));

        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/product-images/{firstId}/", new { alt_text = "Nueva", is_main = true, order = 0, product = 1 }));
        Assert.Equal("Nueva", updated.GetProperty("alt_text").GetString());
        Assert.True(updated.GetProperty("is_main").GetBoolean());

        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/product-images/{thirdId}/")).StatusCode);
        var afterNonMainDelete = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=1"));
        Assert.Equal(2, afterNonMainDelete.GetArrayLength());
        Assert.Single(afterNonMainDelete.EnumerateArray().Where(image => image.GetProperty("is_main").GetBoolean()));

        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/product-images/{firstId}/")).StatusCode);
        var afterDelete = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=1"));
        Assert.Single(afterDelete.EnumerateArray());
        Assert.Equal(secondId, afterDelete[0].GetProperty("id").GetInt32());
        Assert.True(afterDelete[0].GetProperty("is_main").GetBoolean());

        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/product-images/{secondId}/")).StatusCode);
        var empty = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=1"));
        Assert.Empty(empty.EnumerateArray());
    }

    [Fact]
    public async Task ProductImageWriteValidatesAuthRelationsAndFiles()
    {
        await _factory.SeedCommercialDataAsync();
        using var anonymous = _factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await anonymous.PostAsync("/api/product-images/", ImageForm(1, "uno.jpg", "image/jpeg", JpegBytes()))).StatusCode);

        await _factory.SeedUnauthorizedUserAsync();
        using var viewer = await CreateAuthorizedClientAsync("viewer");
        Assert.Equal(HttpStatusCode.Forbidden, (await viewer.PostAsync("/api/product-images/", ImageForm(1, "uno.jpg", "image/jpeg", JpegBytes()))).StatusCode);

        using var client = await CreateAuthorizedClientAsync();
        Assert.Equal(HttpStatusCode.NotFound, (await client.PostAsync("/api/product-images/", ImageForm(999, "uno.jpg", "image/jpeg", JpegBytes()))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/product-images/", ImageForm(1, "empty.jpg", "image/jpeg", []))).StatusCode);
        var tooLarge = new byte[1024 * 1024 + 1];
        tooLarge[0] = 0xFF; tooLarge[1] = 0xD8; tooLarge[2] = 0xFF;
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/product-images/", ImageForm(1, "large.jpg", "image/jpeg", tooLarge))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/product-images/", ImageForm(1, "bad.gif", "image/gif", [0x47, 0x49, 0x46]))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/product-images/", ImageForm(1, "bad.jpg", "text/plain", JpegBytes()))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/product-images/", ImageForm(1, "bad.jpg", "image/jpeg", [1, 2, 3, 4]))).StatusCode);

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/product-images/", ImageForm(1, "ok.webp", "image/webp", WebpBytes())));
        var imageId = created.GetProperty("id").GetInt32();
        Assert.Equal(HttpStatusCode.NotFound, (await client.PatchAsJsonAsync($"/api/product-images/{imageId}/", new { product = 2, order = 1 })).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.DeleteAsync("/api/product-images/999/")).StatusCode);
    }

    [Fact]
    public async Task ProductImagePublicUrlIsServedByStaticFiles()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/product-images/", ImageForm(1, "public.png", "image/png", PngBytes())));
        var imageUrl = created.GetProperty("image").GetString();

        Assert.False(string.IsNullOrWhiteSpace(imageUrl));
        Assert.DoesNotContain(_factory.UploadRoot, imageUrl, StringComparison.OrdinalIgnoreCase);

        var staticResponse = await client.GetAsync(imageUrl);
        var content = await staticResponse.Content.ReadAsByteArrayAsync();

        Assert.Equal(HttpStatusCode.OK, staticResponse.StatusCode);
        Assert.Equal(PngBytes(), content);
    }

    [Fact]
    public async Task ProductImageDeleteHandlesMissingFilesAndPreservesHistoricalExternalUrls()
    {
        await _factory.SeedCommercialDataAsync();
        using (var scope = _factory.Services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            dbContext.ProductImages.AddRange(
                new ProductImage { Id = 100, ProductId = 1, Image = "/media/product-images/1/missing.jpg", AltText = "Missing", IsMain = true, Order = 0 },
                new ProductImage { Id = 101, ProductId = 1, Image = "https://cdn.example.test/legacy.jpg", AltText = "Legacy", IsMain = false, Order = 1 });
            await dbContext.SaveChangesAsync();
        }

        using var client = await CreateAuthorizedClientAsync();
        var list = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/product-images/?product=1"));
        Assert.Contains(list.EnumerateArray(), image => image.GetProperty("image").GetString() == "https://cdn.example.test/legacy.jpg");

        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync("/api/product-images/100/")).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync("/api/product-images/101/")).StatusCode);

        using var assertScope = _factory.Services.CreateScope();
        var assertContext = assertScope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.False(await assertContext.ProductImages.AnyAsync(image => image.Id == 100 || image.Id == 101));
    }

    [Fact]
    public async Task ProductImageUploadCleansStoredFileWhenSaveChangesFails()
    {
        var factory = new CommercialWriteApiFactory(
            configureTestServices: null,
            configureDbContext: options => options.AddInterceptors(new ThrowingProductImageSaveChangesInterceptor()));
        using var disposableFactory = factory;
        await factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync(factory);

        var response = await client.PostAsync("/api/product-images/", ImageForm(1, "cleanup.jpg", "image/jpeg", JpegBytes(), ThrowingProductImageSaveChangesInterceptor.TriggerAltText));

        Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
        Assert.True(Directory.Exists(factory.UploadRoot));
        Assert.False(Directory.EnumerateFiles(factory.UploadRoot, "*", SearchOption.AllDirectories).Any());

        using var assertScope = factory.Services.CreateScope();
        var assertContext = assertScope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.False(await assertContext.ProductImages.AnyAsync(image => image.AltText == ThrowingProductImageSaveChangesInterceptor.TriggerAltText));
    }

    [Fact]
    public async Task ProductImageDeleteKeepsDatabaseDeletionWhenManagedFileRemovalFails()
    {
        var factory = new CommercialWriteApiFactory(services =>
        {
            services.RemoveAll<IProductImageStorage>();
            services.AddSingleton<IProductImageStorage, ThrowingDeleteProductImageStorage>();
        });
        using var disposableFactory = factory;
        await factory.SeedCommercialDataAsync();

        using (var scope = factory.Services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            dbContext.ProductImages.Add(new ProductImage { Id = 120, ProductId = 1, Image = "/media/product-images/1/fail-delete.jpg", AltText = "Delete failure", IsMain = true, Order = 0 });
            await dbContext.SaveChangesAsync();
        }

        using var client = await CreateAuthorizedClientAsync(factory);
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync("/api/product-images/120/")).StatusCode);

        using var assertScope = factory.Services.CreateScope();
        var assertContext = assertScope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.False(await assertContext.ProductImages.AnyAsync(image => image.Id == 120));
    }

    private static MultipartFormDataContent ImageForm(int productId, string fileName, string contentType, byte[] bytes, string? altText = null, bool? isMain = null, int? order = null)
    {
        var form = new MultipartFormDataContent();
        form.Add(new StringContent(productId.ToString(System.Globalization.CultureInfo.InvariantCulture)), "product");
        var file = new ByteArrayContent(bytes);
        file.Headers.ContentType = new MediaTypeHeaderValue(contentType);
        form.Add(file, "image", fileName);
        if (altText is not null) form.Add(new StringContent(altText), "alt_text");
        if (isMain.HasValue) form.Add(new StringContent(isMain.Value ? "true" : "false"), "is_main");
        if (order.HasValue) form.Add(new StringContent(order.Value.ToString(System.Globalization.CultureInfo.InvariantCulture)), "order");
        return form;
    }

    private static byte[] JpegBytes() => [0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01];
    private static byte[] PngBytes() => [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00];
    private static byte[] WebpBytes() => [0x52, 0x49, 0x46, 0x46, 0x04, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50];

    [Fact]
    public async Task SellerCanManageProductSpecs()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/product-specs/", new { product = 1, name = "Peso", value = "10", unit = "kg" }));
        var specId = created.GetProperty("id").GetInt32();
        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/product-specs/{specId}/", new { value = "11" }));

        Assert.Equal("11", updated.GetProperty("value").GetString());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/product-specs/{specId}/")).StatusCode);
    }

    [Fact]
    public async Task QuoteStatusPatchAcceptsValidStatusAndRejectsInvalidStatus()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync("/api/quote-requests/1/", new { status = QuoteStatuses.Contacted, internal_notes = "Llamar" }));
        var invalid = await client.PatchAsJsonAsync("/api/quote-requests/1/", new { status = "invalid" });

        Assert.Equal(QuoteStatuses.Contacted, updated.GetProperty("status").GetString());
        Assert.Equal(HttpStatusCode.BadRequest, invalid.StatusCode);
    }

    [Fact]
    public async Task SellerCanCreateEditAndSoftDeleteHomeSectionItem()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/home-section-items/", new { section = HomeSections.SparePartsOffers, product = 2, position = 1, is_active = true }));
        var itemId = created.GetProperty("id").GetInt32();
        var updated = await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/home-section-items/{itemId}/", new { position = 2 }));

        Assert.Equal(2, updated.GetProperty("position").GetInt32());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/home-section-items/{itemId}/")).StatusCode);
    }

    [Fact]
    public async Task CommercialReadAuthAndHealthRegressionsStillWorkWithoutSecretsExposure()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var health = await client.GetAsync("/api/health/");
        var me = await client.GetAsync("/api/auth/me/");
        var products = await client.GetAsync("/api/products/?include_unpublished=true");
        var productsBody = await products.Content.ReadAsStringAsync();

        Assert.True(health.IsSuccessStatusCode);
        Assert.True(me.IsSuccessStatusCode);
        Assert.True(products.IsSuccessStatusCode, productsBody);
        Assert.DoesNotContain("password_hash", productsBody, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("token_hash", productsBody, StringComparison.OrdinalIgnoreCase);
    }

    private Task<HttpClient> CreateAuthorizedClientAsync(string username = "demo") => CreateAuthorizedClientAsync(_factory, username);

    private async Task<HttpClient> CreateAuthorizedClientAsync(CommercialWriteApiFactory factory, string username = "demo")
    {
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync("/api/auth/login/", new { username, password = TestPassword });
        var login = await ReadJsonAsync<LoginPayload>(loginResponse);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        return client;
    }

    private static async Task<T> ReadJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response for {typeof(T).Name}. Body: {body}");
        return payload!;
    }

    public sealed class CommercialWriteApiFactory : WebApplicationFactory<Program>
    {
        private readonly Action<IServiceCollection>? _configureTestServices;
        private readonly Action<DbContextOptionsBuilder>? _configureDbContext;
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("CommercialWriteEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();
        private readonly string _uploadRoot = Path.Combine(Path.GetTempPath(), "jemnexus-product-images-" + Guid.NewGuid().ToString("N"));

        public CommercialWriteApiFactory(
            Action<IServiceCollection>? configureTestServices = null,
            Action<DbContextOptionsBuilder>? configureDbContext = null)
        {
            _configureTestServices = configureTestServices;
            _configureDbContext = configureDbContext;
        }

        public string UploadRoot => _uploadRoot;

        public string PhysicalUploadPath(string publicPath)
        {
            var relativePath = publicPath.StartsWith("/media/", StringComparison.OrdinalIgnoreCase)
                ? publicPath["/media/".Length..]
                : publicPath.TrimStart('/');
            return Path.Combine(_uploadRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        }

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configurationBuilder) =>
            {
                var configuration = new Dictionary<string, string?>(TestConfiguration)
                {
                    ["Uploads:RootPath"] = _uploadRoot,
                    ["Uploads:PublicBasePath"] = "/media",
                    ["Uploads:MaxFileSizeMb"] = "1"
                };
                configurationBuilder.AddInMemoryCollection(configuration);
            });
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<JemNexusDbContext>();
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.AddDbContext<JemNexusDbContext>(options =>
                {
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot);
                    _configureDbContext?.Invoke(options);
                });
                _configureTestServices?.Invoke(services);
            });
        }

        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
            if (Directory.Exists(_uploadRoot)) Directory.Delete(_uploadRoot, recursive: true);
        }

        public async Task SeedUnauthorizedUserAsync()
        {
            using var scope = Services.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
            if (await dbContext.AppUsers.AnyAsync(user => user.Username == "viewer")) return;
            var viewer = new AppUser { Username = "viewer", Email = "viewer@example.test", Role = "viewer", IsActive = true, IsStaff = false, IsSuperuser = false };
            viewer.PasswordHash = passwordHasher.HashPassword(viewer, TestPassword);
            dbContext.AppUsers.Add(viewer);
            await dbContext.SaveChangesAsync();
        }

        public async Task SeedCommercialDataAsync()
        {
            using var scope = Services.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            if (await dbContext.Categories.AnyAsync()) return;

            var category = new Category { Id = 1, Name = "Maquinaria", Slug = "maquinaria", ProductType = ProductTypes.Machinery, Description = "Categoría", IsActive = true, Order = 1 };
            var spareCategory = new Category { Id = 2, Name = "Repuestos", Slug = "repuestos", ProductType = ProductTypes.SparePart, Description = "Repuestos", IsActive = true, Order = 2 };
            var brand = new Brand { Id = 1, Name = "ACME", Slug = "acme", Description = "Marca", IsActive = true };
            var supplier = new Supplier { Id = 1, Name = "Proveedor", ContactName = "Contacto", Phone = "+569", Email = "proveedor@example.test", IsActive = true };
            var product = new Product { Id = 1, Name = "Excavadora", Slug = "excavadora", Category = category, Brand = brand, Supplier = supplier, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };
            var spareProduct = new Product { Id = 2, Name = "Filtro", Slug = "filtro", Category = spareCategory, ProductType = ProductTypes.SparePart, Condition = ProductConditions.New, StockStatus = StockStatuses.OnRequest, IsPublished = true };

            dbContext.Categories.AddRange(category, spareCategory);
            dbContext.Brands.Add(brand);
            dbContext.Suppliers.Add(supplier);
            dbContext.Products.AddRange(product, spareProduct);
            dbContext.ProductSpecs.Add(new ProductSpec { Id = 1, Product = product, Key = "Potencia", Value = "100", Unit = "HP" });
            dbContext.QuoteRequests.Add(new QuoteRequest { Id = 1, Product = product, CustomerName = "Cliente", CustomerPhone = "+569", Message = "Cotizar", Status = QuoteStatuses.New });
            dbContext.HomeSectionItems.Add(new HomeSectionItem { Id = 1, Section = HomeSections.MachineryPromotions, Product = product, Position = 1, IsActive = true });
            await dbContext.SaveChangesAsync();
        }
    }

    private static readonly IReadOnlyDictionary<string, string?> TestConfiguration = new Dictionary<string, string?>
    {
        ["Jwt:Issuer"] = "JEM Nexus API Test",
        ["Jwt:Audience"] = "JEM Nexus Frontend Test",
        ["Jwt:Secret"] = "DummyJwtSecretForTests1234567890!",
        ["Jwt:AccessTokenMinutes"] = "60",
        ["Jwt:RefreshTokenDays"] = "7",
        ["JWT_ISSUER"] = "JEM Nexus API Test",
        ["JWT_AUDIENCE"] = "JEM Nexus Frontend Test",
        ["JWT_SECRET"] = "DummyJwtSecretForTests1234567890!",
        ["SeedUsers:SellerUsername"] = "demo",
        ["SeedUsers:SellerPassword"] = TestPassword,
        ["SeedUsers:SellerEmail"] = "demo@example.test",
        ["SeedUsers:SupportUsername"] = "support",
        ["SeedUsers:SupportPassword"] = TestPassword,
        ["SeedUsers:SupportEmail"] = "support@example.test"
    };

    private sealed class ThrowingProductImageSaveChangesInterceptor : SaveChangesInterceptor
    {
        public const string TriggerAltText = "trigger-product-image-save-failure";

        public override InterceptionResult<int> SavingChanges(DbContextEventData eventData, InterceptionResult<int> result)
        {
            ThrowIfTriggered(eventData.Context);
            return base.SavingChanges(eventData, result);
        }

        public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
            DbContextEventData eventData,
            InterceptionResult<int> result,
            CancellationToken cancellationToken = default)
        {
            ThrowIfTriggered(eventData.Context);
            return base.SavingChangesAsync(eventData, result, cancellationToken);
        }

        private static void ThrowIfTriggered(DbContext? context)
        {
            if (context?.ChangeTracker.Entries<ProductImage>().Any(entry =>
                    entry.State == EntityState.Added && entry.Entity.AltText == TriggerAltText) == true)
            {
                throw new InvalidOperationException("Simulated product image SaveChanges failure.");
            }
        }
    }

    private sealed class ThrowingDeleteProductImageStorage : IProductImageStorage
    {
        public Task<StoredProductImage> SaveAsync(int productId, IFormFile file, CancellationToken cancellationToken) =>
            Task.FromResult(new StoredProductImage($"/media/product-images/{productId}/fake.jpg", $"product-images/{productId}/fake.jpg"));

        public Task DeleteIfManagedAsync(string publicPath, CancellationToken cancellationToken) =>
            throw new IOException("Simulated delete failure.");
    }

    private sealed record LoginPayload(string Access, string Refresh, UserPayload User);
    private sealed record UserPayload(int Id, string Username, string? Email, string Role, [property: JsonPropertyName("is_staff")] bool IsStaff, [property: JsonPropertyName("is_superuser")] bool IsSuperuser);
}
