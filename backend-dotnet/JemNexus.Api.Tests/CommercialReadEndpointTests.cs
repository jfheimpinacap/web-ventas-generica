using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.AspNetCore.Hosting;
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
        Assert.True(listDocument.RootElement[0].TryGetProperty("main_image", out _));

        var detail = await client.GetAsync("/api/products/excavadora-demo/");
        var detailBody = await detail.Content.ReadAsStringAsync();

        Assert.True(detail.IsSuccessStatusCode, $"Status: {detail.StatusCode}, Body: {detailBody}");
        using var detailDocument = JsonDocument.Parse(detailBody);
        Assert.Equal("SKU-001", detailDocument.RootElement.GetProperty("sku").GetString());
        Assert.True(detailDocument.RootElement.GetProperty("images").GetArrayLength() > 0);
        Assert.True(detailDocument.RootElement.GetProperty("specs").GetArrayLength() > 0);
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
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();
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
                    ProductType = ProductTypes.SparePart,
                    Condition = ProductConditions.New,
                    ShortDescription = "No publicado",
                    Description = "Producto no publicado",
                    Sku = "SKU-002",
                    StockStatus = StockStatuses.OnRequest,
                    IsPublished = false
                };

                dbContext.Categories.AddRange(category, inactiveCategory);
                dbContext.Brands.Add(brand);
                dbContext.Suppliers.Add(supplier);
                dbContext.Products.AddRange(product, draftProduct);
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
}
