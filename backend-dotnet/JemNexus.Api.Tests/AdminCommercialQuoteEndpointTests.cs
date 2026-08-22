using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
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

public sealed class AdminCommercialQuoteEndpointTests
{
    private const string Password = "Strong-test-password-130!";

    [Fact]
    public async Task SellerIssuesCompleteQuoteInOneRequestWithoutDraft()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        using var response = await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue());
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var quote = await JsonAsync(response);
        Assert.Equal("Issued", quote.GetProperty("status").GetString());
        Assert.StartsWith("COT-", quote.GetProperty("folio").GetString());
        Assert.Equal(200m, quote.GetProperty("net_amount").GetDecimal());
        Assert.Equal(38m, quote.GetProperty("tax_amount").GetDecimal());
        Assert.Equal(238m, quote.GetProperty("total_amount").GetDecimal());
        Assert.Equal(1, quote.GetProperty("items").GetArrayLength());
        Assert.Equal(1, await factory.QuoteCountAsync());
    }

    [Theory]
    [InlineData("support", HttpStatusCode.Forbidden)]
    public async Task OnlySellerCanIssue(string username, HttpStatusCode expected)
    {
        await using var factory = new QuoteApiFactory(); using var client = await factory.AuthorizedClientAsync(username);
        Assert.Equal(expected, (await client.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue())).StatusCode);
        Assert.Equal(0, await factory.QuoteCountAsync());
    }

    [Fact]
    public async Task AnonymousCannotIssue()
    {
        await using var factory = new QuoteApiFactory(); using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue())).StatusCode);
    }

    [Theory]
    [InlineData("bad-rut", "CLP")]
    [InlineData("12.345.678-5", "EUR")]
    public async Task InvalidInputDoesNotPersist(string rut, string currency)
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        Assert.Equal(HttpStatusCode.BadRequest, (await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue(rut, currency))).StatusCode);
        Assert.Equal(0, await factory.QuoteCountAsync());
    }

    [Fact]
    public async Task EmptyItemsAndUnavailableCatalogProductDoNotPersist()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        Assert.Equal(HttpStatusCode.BadRequest, (await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue(items: []))).StatusCode);
        var productId = await factory.AddProductAsync(false, false);
        Assert.Equal(HttpStatusCode.BadRequest, (await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue(items: [new { source = "Catalog", product_id = productId, quantity = 1, unit_net_amount = 100m }]))).StatusCode);
        Assert.Equal(0, await factory.QuoteCountAsync());
    }

    [Fact]
    public async Task LegacyDraftWriteRoutesAreNotExposedAndIssuedQuoteIsReadableOnlyByOwner()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        Assert.Equal(HttpStatusCode.MethodNotAllowed, (await seller.PostAsJsonAsync("/api/admin/commercial-quotes", ValidIssue())).StatusCode);
        Assert.Equal(HttpStatusCode.MethodNotAllowed, (await seller.PutAsJsonAsync("/api/admin/commercial-quotes/1", ValidIssue())).StatusCode);
        var issued = await JsonAsync(await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue()));
        var id = issued.GetProperty("id").GetInt32();
        await factory.AddUserAsync("other", AppRoles.Seller, "VEN-0002"); using var other = await factory.AuthorizedClientAsync("other");
        Assert.Equal(HttpStatusCode.NotFound, (await other.GetAsync($"/api/admin/commercial-quotes/{id}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await seller.GetAsync($"/api/admin/commercial-quotes/{id}")).StatusCode);
    }

    [Fact]
    public async Task TwoIssuesUseDistinctFoliosAndPublicDtoOmitsInternalFields()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        var first = await JsonAsync(await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue()));
        var secondResponse = await seller.PostAsJsonAsync("/api/admin/commercial-quotes/issue", ValidIssue());
        var raw = await secondResponse.Content.ReadAsStringAsync(); var second = JsonDocument.Parse(raw).RootElement;
        Assert.NotEqual(first.GetProperty("folio").GetString(), second.GetProperty("folio").GetString());
        foreach (var forbidden in new[] { "password", "hash", "token", "normalized_rut", "responsible_seller_id", "folio_sequence_number" }) Assert.DoesNotContain(forbidden, raw, StringComparison.OrdinalIgnoreCase);
    }

    private static object ValidIssue(string rut = "12.345.678-5", string currency = "CLP", object[]? items = null) => new
    {
        customer_profile_id = (int?)null, customer_business_name = "ACME enviada", customer_rut = rut, customer_business_activity = "Servicios industriales",
        customer_address = "Calle Uno 123", customer_phone = "+56 9 1234 5678", customer_city_or_commune = "Santiago", customer_contact_name = "Ana Pérez",
        customer_email = (string?)null, currency, sale_condition = "Cash", validity_days = 15, detailed_description = (string?)null,
        items = items ?? [new { source = "FreeText", product_name = "Servicio", quantity = 2, unit_net_amount = 100m, discount_percent = 0m }]
    };
    private static async Task<JsonElement> JsonAsync(HttpResponseMessage response) => JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.Clone();

    public sealed class QuoteApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _name = InMemoryTestDatabase.CreateDatabaseName("AdminCommercialQuoteEndpointTests");
        private readonly InMemoryDatabaseRoot _root = InMemoryTestDatabase.CreateDatabaseRoot();
        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Issuer"] = "Quote API Test", ["Jwt:Audience"] = "Quote Frontend Test", ["Jwt:Secret"] = "quote-api-test-secret-not-for-production-32chars",
                ["SeedUsers:SellerUsername"] = "seller", ["SeedUsers:SellerPassword"] = Password, ["SeedUsers:SellerEmail"] = "seller@example.test",
                ["SeedUsers:SupportUsername"] = "support", ["SeedUsers:SupportPassword"] = Password, ["SeedUsers:SupportEmail"] = "support@example.test"
            }));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>(); services.RemoveAll<ISellerCodeGenerator>();
                services.AddSingleton<ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.AddDbContext<JemNexusDbContext>(options => InMemoryTestDatabase.Configure(options, _name, _root));
            });
        }
        public async Task<HttpClient> AuthorizedClientAsync(string username)
        {
            var client = CreateClient(); var login = await client.PostAsJsonAsync("/api/auth/login", new { username, password = Password });
            Assert.Equal(HttpStatusCode.OK, login.StatusCode); var json = await JsonAsync(login);
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", json.GetProperty("access").GetString()); return client;
        }
        public async Task AddUserAsync(string username, string role, string? sellerCode)
        {
            using var scope = Services.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>(); var hasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
            var user = new AppUser { Username = username, Role = role, SellerCode = sellerCode, FullName = username, IsActive = true, IsStaff = true }; user.PasswordHash = hasher.HashPassword(user, Password); db.Add(user); await db.SaveChangesAsync();
        }
        public async Task<(int ProfileId, int ProductId)> AddCatalogDataAsync()
        {
            using var scope = Services.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var profile = new CustomerProfile { BusinessName = "Perfil original", NormalizedBusinessName = "PERFIL ORIGINAL", Rut = "12345678-5", NormalizedRut = "12345678-5", BusinessActivity = "Giro", Address = "Dirección", Phone = "12345", CityOrCommune = "Ciudad", ContactName = "Contacto" };
            var category = new Category { Name = "Categoría", Slug = "categoria", ProductType = ProductTypes.Machinery }; var brand = new Brand { Name = "Marca real", Slug = "marca-real" };
            var product = new Product { Name = "Producto real", Slug = "producto-real", Category = category, Brand = brand, Model = "Modelo real", ProductType = ProductTypes.Machinery, IsPublished = true, StockStatus = StockStatuses.Available };
            db.AddRange(profile, product); await db.SaveChangesAsync(); return (profile.Id, product.Id);
        }
        public async Task<int> AddProductAsync(bool published, bool sold)
        {
            using var scope = Services.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var category = new Category { Name = Guid.NewGuid().ToString(), Slug = Guid.NewGuid().ToString(), ProductType = ProductTypes.Machinery };
            var product = new Product { Name = "Estado producto", Slug = Guid.NewGuid().ToString(), Category = category, ProductType = ProductTypes.Machinery, IsPublished = published, StockStatus = sold ? StockStatuses.Sold : StockStatuses.Available };
            db.Add(product); await db.SaveChangesAsync(); return product.Id;
        }
        public async Task<int> QuoteCountAsync() { using var scope = Services.CreateScope(); return await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().CommercialQuotes.CountAsync(); }
        public async Task SetStatusAsync(int id, string status) { using var scope = Services.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>(); db.Entry((await db.CommercialQuotes.FindAsync(id))!).Property(nameof(CommercialQuote.Status)).CurrentValue = status; await db.SaveChangesAsync(); }
        public async Task<string> ProfileBusinessNameAsync(int id) { using var scope = Services.CreateScope(); return (await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().CustomerProfiles.FindAsync(id))!.BusinessName; }
        public async Task<string> ProductNameAsync(int id) { using var scope = Services.CreateScope(); return (await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().Products.FindAsync(id))!.Name; }
    }
}
