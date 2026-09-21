using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services.ProductImages;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialReadEndpointTests : IClassFixture<CommercialReadEndpointTests.CommercialApiFactory>
{
    private const string TestPassword = "DummyPassword123!";
    private readonly CommercialApiFactory _factory;

    public CommercialReadEndpointTests(CommercialApiFactory factory)
    {
        _factory = factory;
    }

    [Theory]
    [InlineData("/api/products/")]
    [InlineData("/api/categories/")]
    [InlineData("/api/brands/")]
    [InlineData("/api/suppliers/")]
    [InlineData("/api/promotions/")]
    [InlineData("/api/quote-requests/")]
    [InlineData("/api/home-section-items/")]
    public async Task CommercialReadEndpointsRequireBearerToken(string path)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/products/")]
    [InlineData("/api/categories/")]
    [InlineData("/api/brands/")]
    [InlineData("/api/suppliers/")]
    [InlineData("/api/promotions/")]
    [InlineData("/api/quote-requests/")]
    [InlineData("/api/home-section-items/")]
    public async Task SellerCanListCommercialReadEndpoints(string path)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var response = await client.GetAsync(path);
        var body = await response.Content.ReadAsStringAsync();

        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        Assert.NotEqual("[]", body);
        Assert.DoesNotContain("password_hash", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("token_hash", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("refresh", body, StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData("/api/product-images/?product=1")]
    [InlineData("/api/product-specs/?product=1")]
    public async Task SellerCanListProductReadCompanionEndpoints(string path)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var response = await client.GetAsync(path);
        var body = await response.Content.ReadAsStringAsync();

        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        Assert.NotEqual("[]", body);
        Assert.DoesNotContain("password_hash", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("token_hash", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task ProductFiltersAndDetailWorkForSeller()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var filtered = await client.GetAsync("/api/products/?search=excavadora&category=maquinaria&brand=acme&product_type=machinery&condition=used&stock_status=available&include_unpublished=true&ordering=name");
        var filteredBody = await filtered.Content.ReadAsStringAsync();

        Assert.True(filtered.IsSuccessStatusCode, $"Status: {filtered.StatusCode}, Body: {filteredBody}");
        using var listDocument = JsonDocument.Parse(filteredBody);
        Assert.Equal(JsonValueKind.Array, listDocument.RootElement.ValueKind);
        Assert.Single(listDocument.RootElement.EnumerateArray());
        Assert.Equal("excavadora-demo", listDocument.RootElement[0].GetProperty("slug").GetString());
        Assert.Equal("EX-100", listDocument.RootElement[0].GetProperty("model").GetString());
        Assert.True(listDocument.RootElement[0].TryGetProperty("main_image", out _));

        var detail = await client.GetAsync("/api/products/excavadora-demo/");
        var detailBody = await detail.Content.ReadAsStringAsync();

        Assert.True(detail.IsSuccessStatusCode, $"Status: {detail.StatusCode}, Body: {detailBody}");
        using var detailDocument = JsonDocument.Parse(detailBody);
        Assert.Equal(JsonValueKind.Null, detailDocument.RootElement.GetProperty("sku").ValueKind);
        Assert.True(detailDocument.RootElement.GetProperty("images").GetArrayLength() > 0);
        Assert.True(detailDocument.RootElement.GetProperty("specs").GetArrayLength() > 0);

        var machinerySkuSearch = await ReadSuccessfulJsonAsync<JsonElement>(
            await client.GetAsync("/api/products/?search=SKU-001&include_unpublished=true"));
        Assert.Empty(machinerySkuSearch.EnumerateArray());

        var sparePartSkuSearch = await ReadSuccessfulJsonAsync<JsonElement>(
            await client.GetAsync("/api/products/?search=SKU-002&include_unpublished=true"));
        Assert.Single(sparePartSkuSearch.EnumerateArray());
        Assert.Equal("repuesto-borrador", sparePartSkuSearch[0].GetProperty("slug").GetString());

        var sparePartDetail = await ReadSuccessfulJsonAsync<JsonElement>(
            await client.GetAsync("/api/products/repuesto-borrador/"));
        Assert.Equal("SKU-002", sparePartDetail.GetProperty("sku").GetString());
    }

    [Fact]
    public async Task SellerCanListSoldProductsWithAdministrativeFilter()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var response = await client.GetAsync($"/api/products/?stock_status={StockStatuses.Sold}&include_unpublished=true");
        var body = await response.Content.ReadAsStringAsync();

        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        using var document = JsonDocument.Parse(body);
        Assert.Contains(document.RootElement.EnumerateArray(), product => product.GetProperty("slug").GetString() == "producto-vendido-admin");
    }

    [Fact]
    public async Task CompleteCommercialTargetsExposeDraftRelationsAndProtectedMediaWithoutChangingPublicEligibility()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        foreach (var (path, hiddenId) in new[] { ("/api/products", 2), ("/api/categories", 2), ("/api/brands", 2), ("/api/suppliers", 2) })
        {
            var filtered = await ReadSuccessfulJsonAsync<JsonElement>(await client.GetAsync(path));
            Assert.DoesNotContain(filtered.EnumerateArray(), item => item.GetProperty("id").GetInt32() == hiddenId);
        }

        foreach (var (path, includedId) in new[] { ("/api/categories?include_inactive=true", 2), ("/api/brands?include_inactive=true", 2), ("/api/suppliers?include_inactive=true", 2) })
        {
            var complete = await ReadSuccessfulJsonAsync<JsonElement>(await client.GetAsync(path));
            Assert.Contains(complete.EnumerateArray(), item => item.GetProperty("id").GetInt32() == includedId);
        }

        var products = await ReadSuccessfulJsonAsync<JsonElement>(await client.GetAsync("/api/products?include_unpublished=true"));
        var draft = products.EnumerateArray().Single(item => item.GetProperty("id").GetInt32() == 2);
        Assert.Equal(2, draft.GetProperty("category_id").GetInt32());
        Assert.Equal(2, draft.GetProperty("brand_id").GetInt32());
        Assert.Equal(2, draft.GetProperty("supplier_id").GetInt32());
        Assert.Equal(2, draft.GetProperty("technical_sheet_id").GetInt32());
        Assert.False(draft.GetProperty("is_published").GetBoolean());
        Assert.Equal("spare_part", draft.GetProperty("product_type").GetString());
        Assert.Equal("new", draft.GetProperty("condition").GetString());
        Assert.Equal("No publicado", draft.GetProperty("short_description").GetString());
        Assert.Equal("Producto no publicado", draft.GetProperty("description").GetString());
        Assert.Equal("REP-200", draft.GetProperty("model").GetString());
        Assert.Equal("SKU-002", draft.GetProperty("sku").GetString());
        Assert.Equal(2.5m, draft.GetProperty("working_height_m").GetDecimal());
        Assert.Equal(2024, draft.GetProperty("year").GetInt32());
        Assert.Equal(12, draft.GetProperty("hours_meter").GetInt32());
        Assert.True(draft.GetProperty("includes_technical_review").GetBoolean());
        Assert.True(draft.GetProperty("includes_commercial_technical_advice").GetBoolean());
        Assert.True(draft.GetProperty("includes_coordinated_delivery").GetBoolean());
        Assert.Equal(9876.54m, draft.GetProperty("price").GetDecimal());
        Assert.False(draft.GetProperty("price_visible").GetBoolean());
        Assert.Equal("on_request", draft.GetProperty("stock_status").GetString());
        Assert.False(draft.GetProperty("is_featured").GetBoolean());
        Assert.Equal(2, draft.GetProperty("category").GetProperty("id").GetInt32());
        Assert.Equal(2, draft.GetProperty("brand").GetProperty("id").GetInt32());
        Assert.Equal(2, draft.GetProperty("main_image").GetProperty("id").GetInt32());
        Assert.NotEqual(default, draft.GetProperty("created_at").GetDateTimeOffset());
        Assert.NotEqual(default, draft.GetProperty("updated_at").GetDateTimeOffset());

        var images = await ReadSuccessfulJsonAsync<JsonElement>(await client.GetAsync("/api/product-images"));
        var image = images.EnumerateArray().Single(item => item.GetProperty("id").GetInt32() == 2);
        Assert.Equal(2, image.GetProperty("product").GetInt32());
        var fileUrl = image.GetProperty("file_url").GetString();
        Assert.Equal("/api/product-images/2/file", fileUrl);
        using var file = await client.GetAsync(fileUrl);
        Assert.Equal(HttpStatusCode.OK, file.StatusCode);
        Assert.Equal("image/png", file.Content.Headers.ContentType?.MediaType);
        Assert.Equal(TestProductImageStorage.DraftBytes, await file.Content.ReadAsByteArrayAsync());
        using var anonymous = _factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await anonymous.GetAsync(fileUrl)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await anonymous.GetAsync("/media/products/draft.png")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await anonymous.GetAsync("/api/public/products/repuesto-borrador/technical-sheet/file")).StatusCode);

        var specs = await ReadSuccessfulJsonAsync<JsonElement>(await client.GetAsync("/api/product-specs"));
        Assert.Contains(specs.EnumerateArray(), item => item.GetProperty("product").GetInt32() == 2 && item.GetProperty("name").GetString() == "Código");
        var body = products.GetRawText() + images.GetRawText() + specs.GetRawText();
        foreach (var secret in new[] { "storage_key", "physical", "password", "password_hash", "token", "token_hash", "refresh" })
            Assert.DoesNotContain(secret, body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task QuoteRequestFiltersWorkForSeller()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();

        var response = await client.GetAsync("/api/quote-requests/?status=new&search=cliente&ordering=-created_at");
        var body = await response.Content.ReadAsStringAsync();

        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        using var document = JsonDocument.Parse(body);
        Assert.Single(document.RootElement.EnumerateArray());
        Assert.Equal("new", document.RootElement[0].GetProperty("status").GetString());
        Assert.True(document.RootElement[0].TryGetProperty("product_name", out _));
    }

    [Fact]
    public async Task AuthMeStillWorksAfterCommercialEndpointsAreMapped()
    {
        using var client = await CreateAuthorizedClientAsync();

        var response = await client.GetAsync("/api/auth/me/");
        var body = await response.Content.ReadAsStringAsync();

        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        Assert.Contains("demo", body, StringComparison.OrdinalIgnoreCase);
    }

    private async Task<HttpClient> CreateAuthorizedClientAsync()
    {
        var client = _factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = TestPassword });
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(loginResponse);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        return client;
    }

    private static async Task<T> ReadSuccessfulJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");

        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response body for {typeof(T).Name}. Status: {response.StatusCode}, Body: {body}");

        return payload!;
    }

    public sealed class CommercialApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("CommercialReadEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.GetSharedDatabaseRoot();
        private readonly SemaphoreSlim _seedLock = new(1, 1);
        private bool _seeded;

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configurationBuilder) =>
            {
                configurationBuilder.AddInMemoryCollection(TestConfiguration);
            });
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<JemNexus.Api.Services.ISellerCodeGenerator>();
                services.AddSingleton<JemNexus.Api.Services.ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.RemoveAll<IProductImageStorage>();
                services.AddSingleton<IProductImageStorage, TestProductImageStorage>();
                services.AddDbContext<JemNexusDbContext>(options =>
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }

        public async Task SeedCommercialDataAsync()
        {
            await _seedLock.WaitAsync();
            try
            {
                if (_seeded)
                {
                    return;
                }

                using var scope = Services.CreateScope();
                var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();

                var category = new Category
                {
                    Id = 1,
                    Name = "Maquinaria",
                    Slug = "maquinaria",
                    Description = "Categoría de maquinaria",
                    IsActive = true,
                    Order = 1
                };
                var inactiveCategory = new Category
                {
                    Id = 2,
                    Name = "Inactiva",
                    Slug = "inactiva",
                    Description = "Categoría inactiva",
                    IsActive = false,
                    Order = 2
                };
                var brand = new Brand
                {
                    Id = 1,
                    Name = "ACME",
                    Slug = "acme",
                    Description = "Marca demo",
                    IsActive = true
                };
                var inactiveBrand = new Brand { Id = 2, Name = "Inactive Brand", Slug = "inactive-brand", Description = "Inactive", IsActive = false };
                var supplier = new Supplier
                {
                    Id = 1,
                    Name = "Proveedor Demo",
                    ContactName = "Contacto Demo",
                    Phone = "+56900000000",
                    Email = "proveedor@example.test",
                    Notes = "Notas internas",
                    IsActive = true
                };
                var inactiveSupplier = new Supplier { Id = 2, Name = "Inactive Supplier", ContactName = "Private", Phone = "+56922222222", Email = "inactive@example.test", Notes = "Private", IsActive = false };
                var draftSheet = new TechnicalSheet { Id = 2, Name = "Draft sheet", OriginalFileName = "draft.pdf", StorageKey = "private/draft.pdf", ContentType = "application/pdf", SizeBytes = 12 };
                var product = new Product
                {
                    Id = 1,
                    Name = "Excavadora Demo",
                    Slug = "excavadora-demo",
                    Category = category,
                    Brand = brand,
                    Supplier = supplier,
                    ProductType = ProductTypes.Machinery,
                    Condition = ProductConditions.Used,
                    ShortDescription = "Equipo para pruebas",
                    Description = "Detalle del equipo",
                    Model = "EX-100",
                    Sku = "SKU-001",
                    Year = 2020,
                    HoursMeter = 1500,
                    Price = 123456.78m,
                    PriceVisible = true,
                    StockStatus = StockStatuses.Available,
                    IsFeatured = true,
                    IsPublished = true
                };
                var draftProduct = new Product
                {
                    Id = 2,
                    Name = "Repuesto Borrador",
                    Slug = "repuesto-borrador",
                    Category = inactiveCategory,
                    Brand = inactiveBrand,
                    Supplier = inactiveSupplier,
                    TechnicalSheet = draftSheet,
                    ProductType = ProductTypes.SparePart,
                    Condition = ProductConditions.New,
                    ShortDescription = "No publicado",
                    Description = "Producto no publicado",
                    Model = "REP-200",
                    Sku = "SKU-002",
                    WorkingHeightM = 2.5m,
                    Year = 2024,
                    HoursMeter = 12,
                    IncludesTechnicalReview = true,
                    IncludesCommercialTechnicalAdvice = true,
                    IncludesCoordinatedDelivery = true,
                    Price = 9876.54m,
                    PriceVisible = false,
                    StockStatus = StockStatuses.OnRequest,
                    IsPublished = false
                };
                var soldProduct = new Product
                {
                    Id = 3,
                    Name = "Producto Vendido Admin",
                    Slug = "producto-vendido-admin",
                    Category = category,
                    ProductType = ProductTypes.Machinery,
                    Condition = ProductConditions.Used,
                    StockStatus = StockStatuses.Sold,
                    IsPublished = true
                };

                dbContext.Categories.AddRange(category, inactiveCategory);
                dbContext.Brands.AddRange(brand, inactiveBrand);
                dbContext.Suppliers.AddRange(supplier, inactiveSupplier);
                dbContext.TechnicalSheets.Add(draftSheet);
                dbContext.Products.AddRange(product, draftProduct, soldProduct);
                dbContext.ProductImages.Add(new ProductImage
                {
                    Id = 1,
                    Product = product,
                    Image = "/media/products/excavadora.jpg",
                    AltText = "Excavadora Demo",
                    IsMain = true,
                    Order = 1
                });
                dbContext.ProductSpecs.Add(new ProductSpec
                {
                    Id = 1,
                    Product = product,
                    Key = "Potencia",
                    Value = "100",
                    Unit = "HP",
                    Order = 1
                });
                dbContext.ProductImages.Add(new ProductImage { Id = 2, Product = draftProduct, Image = "/media/products/draft.png", AltText = "Draft", IsMain = true, Order = 0 });
                dbContext.ProductSpecs.Add(new ProductSpec { Id = 2, Product = draftProduct, Key = "Código", Value = "DRAFT", Unit = "", Order = 0 });
                dbContext.Promotions.Add(new Promotion
                {
                    Id = 1,
                    Title = "Promoción Demo",
                    Subtitle = "Subtítulo",
                    Product = product,
                    Image = "/media/promotions/demo.jpg",
                    ButtonText = "Ver",
                    ButtonUrl = "/producto/excavadora-demo",
                    IsActive = true,
                    Order = 1
                });
                dbContext.QuoteRequests.Add(new QuoteRequest
                {
                    Id = 1,
                    Product = product,
                    CustomerName = "Cliente Demo",
                    CustomerPhone = "+56911111111",
                    CustomerEmail = "cliente@example.test",
                    CompanyName = "Empresa Demo",
                    City = "Santiago",
                    PreferredContactMethod = PreferredContactMethods.Email,
                    Message = "Necesito cotización",
                    Status = QuoteStatuses.New,
                    InternalNotes = "Nota privada",
                    SellerResponse = "Respuesta interna"
                });
                dbContext.HomeSectionItems.Add(new HomeSectionItem
                {
                    Id = 1,
                    Section = HomeSections.MachineryPromotions,
                    Position = 1,
                    Product = product,
                    IsActive = true
                });

                await dbContext.SaveChangesAsync();
                _seeded = true;
            }
            finally
            {
                _seedLock.Release();
            }
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
    private sealed class TestProductImageStorage : IProductImageStorage
    {
        public static readonly byte[] DraftBytes = [0x89, 0x50, 0x4e, 0x47, 1, 2, 3];
        public Task<StoredProductImage> SaveAsync(int productId, IFormFile file, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<Stream?> OpenReadAsync(string publicPath, CancellationToken cancellationToken) => Task.FromResult<Stream?>(publicPath == "/media/products/draft.png" ? new MemoryStream(DraftBytes, writable: false) : null);
        public Task DeleteIfManagedAsync(string publicPath, CancellationToken cancellationToken) => Task.CompletedTask;
    }
}
