using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
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

    private async Task<HttpClient> CreateAuthorizedClientAsync(string username = "demo")
    {
        var client = _factory.CreateClient();
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
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("CommercialWriteEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configurationBuilder) => configurationBuilder.AddInMemoryCollection(TestConfiguration));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.AddDbContext<JemNexusDbContext>(options => InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
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

    private sealed record LoginPayload(string Access, string Refresh, UserPayload User);
    private sealed record UserPayload(int Id, string Username, string? Email, string Role, [property: JsonPropertyName("is_staff")] bool IsStaff, [property: JsonPropertyName("is_superuser")] bool IsSuperuser);
}
