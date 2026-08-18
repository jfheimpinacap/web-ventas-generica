using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
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

namespace JemNexus.Api.Tests;

public sealed class AdminCommercialQuoteEndpointTests
{
    private const string Password = "Strong-test-password-130!";

    [Fact]
    public void SupportFunctionalUsernameUsesHistoricalPersistedRole()
    {
        Assert.Equal("support_admin", AppRoles.SupportAdmin);
    }

    [Theory]
    [InlineData("GET", "/api/admin/commercial-quotes")]
    [InlineData("GET", "/api/admin/commercial-quotes/1")]
    [InlineData("POST", "/api/admin/commercial-quotes")]
    [InlineData("PUT", "/api/admin/commercial-quotes/1")]
    public async Task AnonymousRequestsAreUnauthorized(string method, string path)
    {
        await using var factory = new QuoteApiFactory();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method is "POST" or "PUT") request.Content = JsonContent.Create(ValidDraft());
        using var response = await factory.CreateClient().SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task SellerCanCreateReadListAndReplaceDraftWithBackendCalculations()
    {
        await using var factory = new QuoteApiFactory();
        using var seller = await factory.AuthorizedClientAsync("seller");
        using var created = await seller.PostAsJsonAsync("/api/admin/commercial-quotes", ValidDraft(items:
        [
            new { source = "FreeText", product_name = "Servicio", quantity = 2, unit_net_amount = 100.55m, discount_percent = 10m }
        ]));
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        var body = await JsonAsync(created);
        Assert.Equal("Draft", body.GetProperty("status").GetString());
        Assert.Equal("VEN-0001", body.GetProperty("seller_code").GetString());
        Assert.Equal(181m, body.GetProperty("net_amount").GetDecimal());
        Assert.Equal(34m, body.GetProperty("tax_amount").GetDecimal());
        Assert.Equal(215m, body.GetProperty("total_amount").GetDecimal());
        Assert.Equal(1, body.GetProperty("items")[0].GetProperty("position").GetInt32());
        var id = body.GetProperty("id").GetInt32();

        Assert.Equal(HttpStatusCode.OK, (await seller.GetAsync($"/api/admin/commercial-quotes/{id}")).StatusCode);
        var list = await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?search=ACME&currency=CLP&page=1&page_size=10"));
        Assert.Equal(1, list.GetProperty("count").GetInt32());
        Assert.False(list.GetProperty("results")[0].TryGetProperty("items", out _));

        using var updated = await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", ValidDraft(currency: "USD", items: []));
        Assert.Equal(HttpStatusCode.OK, updated.StatusCode);
        var update = await JsonAsync(updated);
        Assert.Equal("USD", update.GetProperty("currency").GetString());
        Assert.Equal(0m, update.GetProperty("total_amount").GetDecimal());
        Assert.Empty(update.GetProperty("items").EnumerateArray());
    }

    [Fact]
    public async Task CatalogSnapshotsComeFromPublishedProductAndLinkedProfileDoesNotOverwriteCustomerSnapshot()
    {
        await using var factory = new QuoteApiFactory();
        var (profileId, productId) = await factory.AddCatalogDataAsync();
        using var seller = await factory.AuthorizedClientAsync("seller");
        var payload = ValidDraft(profileId: profileId, items: [new { source = "Catalog", product_id = productId, product_name = "FORGED", brand_name = "FORGED", quantity = 1, unit_net_amount = 10.25m }]);
        var body = await JsonAsync(await seller.PostAsJsonAsync("/api/admin/commercial-quotes", payload));
        Assert.Equal("ACME enviada", body.GetProperty("customer_business_name").GetString());
        Assert.Equal("Producto real", body.GetProperty("items")[0].GetProperty("product_name").GetString());
        Assert.Equal("Marca real", body.GetProperty("items")[0].GetProperty("brand_name").GetString());
    }

    [Fact]
    public async Task SellerIsolationAndSupportReadOnlyAccessUseNotFoundAndForbidden()
    {
        await using var factory = new QuoteApiFactory();
        await factory.AddUserAsync("seller2", AppRoles.Seller, "VEN-0002");
        using var seller = await factory.AuthorizedClientAsync("seller");
        var created = await JsonAsync(await seller.PostAsJsonAsync("/api/admin/commercial-quotes", ValidDraft()));
        var id = created.GetProperty("id").GetInt32();
        using var second = await factory.AuthorizedClientAsync("seller2");
        Assert.Equal(HttpStatusCode.NotFound, (await second.GetAsync($"/api/admin/commercial-quotes/{id}")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await second.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", ValidDraft())).StatusCode);
        Assert.Equal(0, (await JsonAsync(await second.GetAsync("/api/admin/commercial-quotes"))).GetProperty("count").GetInt32());
        Assert.Equal(HttpStatusCode.Created, (await second.PostAsJsonAsync("/api/admin/commercial-quotes", ValidDraft())).StatusCode);

        using var support = await factory.AuthorizedClientAsync("support");
        Assert.Equal(1, (await JsonAsync(await support.GetAsync("/api/admin/commercial-quotes?search=VEN-0001"))).GetProperty("count").GetInt32());
        Assert.Equal(2, (await JsonAsync(await support.GetAsync("/api/admin/commercial-quotes"))).GetProperty("count").GetInt32());
        Assert.Equal(HttpStatusCode.OK, (await support.GetAsync($"/api/admin/commercial-quotes/{id}")).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await support.PostAsJsonAsync("/api/admin/commercial-quotes", ValidDraft())).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await support.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", ValidDraft())).StatusCode);
    }

    [Fact]
    public async Task OtherRoleIsForbiddenAndInvalidCompleteReplacementIsAtomic()
    {
        await using var factory = new QuoteApiFactory();
        await factory.AddUserAsync("viewer", "viewer", null);
        using var viewer = await factory.AuthorizedClientAsync("viewer");
        foreach (var request in new[] { new HttpRequestMessage(HttpMethod.Get, "/api/admin/commercial-quotes"), new HttpRequestMessage(HttpMethod.Get, "/api/admin/commercial-quotes/1"), new HttpRequestMessage(HttpMethod.Post, "/api/admin/commercial-quotes") })
        { if (request.Method == HttpMethod.Post) request.Content = JsonContent.Create(ValidDraft()); using (request) Assert.Equal(HttpStatusCode.Forbidden, (await viewer.SendAsync(request)).StatusCode); }

        using var seller = await factory.AuthorizedClientAsync("seller");
        var id = (await JsonAsync(await seller.PostAsJsonAsync("/api/admin/commercial-quotes", ValidDraft(items: [new { source = "FreeText", product_name = "Original", quantity = 1, unit_net_amount = 100m }])))).GetProperty("id").GetInt32();
        using var invalid = await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", ValidDraft(rut: "invalid", items: [new { source = "FreeText", product_name = "", quantity = 0, unit_net_amount = -1m, discount_percent = 101m }]));
        Assert.Equal(HttpStatusCode.BadRequest, invalid.StatusCode);
        var unchanged = await JsonAsync(await seller.GetAsync($"/api/admin/commercial-quotes/{id}"));
        Assert.Equal("Original", unchanged.GetProperty("items")[0].GetProperty("product_name").GetString());
        Assert.Equal(100m, unchanged.GetProperty("net_amount").GetDecimal());
    }

    [Theory]
    [InlineData("customer_business_name", "")]
    [InlineData("customer_rut", "")]
    [InlineData("customer_rut", "not-a-rut")]
    [InlineData("customer_business_activity", "")]
    [InlineData("customer_address", "")]
    [InlineData("customer_phone", "")]
    [InlineData("customer_city_or_commune", "")]
    [InlineData("customer_contact_name", "")]
    [InlineData("customer_email", "invalid")]
    [InlineData("detailed_description", "__TOO_LONG__")]
    [InlineData("validity_days", "0")]
    [InlineData("validity_days", "-1")]
    [InlineData("currency", "EUR")]
    [InlineData("sale_condition", "Unknown")]
    public async Task InvalidCustomerOrCommercialFieldReturnsValidationWithoutPersistence(string field, string value)
    {
        await using var factory = new QuoteApiFactory();
        using var seller = await factory.AuthorizedClientAsync("seller");
        var payload = DraftNode();
        payload[field] = field switch
        {
            "validity_days" => int.Parse(value),
            "detailed_description" => new string('x', 1001),
            _ => value
        };

        using var response = await seller.PostAsJsonAsync("/api/admin/commercial-quotes", payload);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal(0, await factory.QuoteCountAsync());
    }

    [Theory]
    [InlineData("quantity", "0")]
    [InlineData("quantity", "-1")]
    [InlineData("unit_net_amount", "0")]
    [InlineData("unit_net_amount", "-1")]
    [InlineData("discount_percent", "-0.01")]
    [InlineData("discount_percent", "100.01")]
    [InlineData("discount_percent", "1.001")]
    [InlineData("source", "Unknown")]
    [InlineData("catalog_missing_product", "0")]
    [InlineData("catalog_unknown_product", "0")]
    [InlineData("catalog_unpublished", "0")]
    [InlineData("catalog_sold", "0")]
    [InlineData("free_text_empty_name", "0")]
    [InlineData("free_text_with_product", "0")]
    public async Task InvalidItemReturnsPositionedValidationWithoutPersistence(string scenario, string value)
    {
        await using var factory = new QuoteApiFactory();
        using var seller = await factory.AuthorizedClientAsync("seller");
        var item = FreeItem();
        if (scenario is "quantity") item[scenario] = int.Parse(value);
        else if (scenario is "unit_net_amount" or "discount_percent") item[scenario] = decimal.Parse(value, System.Globalization.CultureInfo.InvariantCulture);
        else if (scenario is "source") item[scenario] = value;
        else if (scenario == "catalog_missing_product") { item["source"] = "Catalog"; item["product_id"] = null; }
        else if (scenario == "catalog_unknown_product") { item["source"] = "Catalog"; item["product_id"] = 999999; }
        else if (scenario is "catalog_unpublished" or "catalog_sold")
        {
            var productId = await factory.AddProductAsync(published: scenario != "catalog_unpublished", sold: scenario == "catalog_sold");
            item["source"] = "Catalog"; item["product_id"] = productId;
        }
        else if (scenario == "free_text_empty_name") item["product_name"] = "";
        else if (scenario == "free_text_with_product") item["product_id"] = 1;
        var payload = DraftNode(); payload["items"] = new JsonArray(item);

        using var response = await seller.PostAsJsonAsync("/api/admin/commercial-quotes", payload);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Contains("items[0]", await response.Content.ReadAsStringAsync());
        Assert.Equal(0, await factory.QuoteCountAsync());
    }

    [Theory]
    [InlineData("GET", "/api/admin/commercial-quotes")]
    [InlineData("GET", "/api/admin/commercial-quotes/1")]
    [InlineData("POST", "/api/admin/commercial-quotes")]
    [InlineData("PUT", "/api/admin/commercial-quotes/1")]
    public async Task EveryDraftRouteForbidsUnrelatedRole(string method, string path)
    {
        await using var factory = new QuoteApiFactory();
        await factory.AddUserAsync("auditor", "auditor", null);
        using var client = await factory.AuthorizedClientAsync("auditor");
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method is "POST" or "PUT") request.Content = JsonContent.Create(ValidDraft());
        Assert.Equal(HttpStatusCode.Forbidden, (await client.SendAsync(request)).StatusCode);
    }

    [Fact]
    public async Task CreationDefaultsNormalizesAndIgnoresAllOverpostedValues()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        var payload = DraftNode(); payload.Remove("validity_days"); payload["customer_email"] = "  "; payload["seller_user_id"] = 999; payload["seller_code"] = "FORGED";
        payload["status"] = "Issued"; payload["tax_rate_percent"] = 1; payload["net_amount"] = 1; payload["tax_amount"] = 1; payload["total_amount"] = 1;
        payload["created_at"] = "2000-01-01T00:00:00Z"; payload["updated_at"] = "2000-01-01T00:00:00Z";
        var first = FreeItem(); first["position"] = 90; first["currency"] = "USD"; first["final_unit_net_amount"] = 1; first["line_net_amount"] = 1;
        var second = FreeItem("Segundo", 2, 50m, 100m); second["position"] = 90; payload["items"] = new JsonArray(first, second);
        using var response = await seller.PostAsJsonAsync("/api/admin/commercial-quotes", payload); Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var json = await JsonAsync(response); Assert.Equal(15, json.GetProperty("validity_days").GetInt32()); Assert.Equal(JsonValueKind.Null, json.GetProperty("customer_email").ValueKind);
        Assert.Equal("Draft", json.GetProperty("status").GetString()); Assert.Equal("VEN-0001", json.GetProperty("seller_code").GetString()); Assert.Equal(19m, json.GetProperty("tax_rate_percent").GetDecimal());
        Assert.Equal("CLP", json.GetProperty("currency").GetString()); Assert.Equal(100m, json.GetProperty("net_amount").GetDecimal()); Assert.Equal(19m, json.GetProperty("tax_amount").GetDecimal()); Assert.Equal(119m, json.GetProperty("total_amount").GetDecimal());
        Assert.Equal(1, json.GetProperty("items")[0].GetProperty("position").GetInt32()); Assert.Equal(2, json.GetProperty("items")[1].GetProperty("position").GetInt32());
        Assert.NotEqual(2000, json.GetProperty("created_at").GetDateTimeOffset().Year);
    }

    [Fact]
    public async Task ListSupportsPaginationFiltersSearchOrderingAndSafeSummary()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        await CreateAsync(seller, DraftNode("Primera Ltda", "CLP", "Cash", "Ana Uno"));
        await Task.Delay(20);
        await CreateAsync(seller, DraftNode("Segunda SpA", "USD", "Credit30Days", "Bruno Dos"));
        var page = await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?page=1&page_size=1")); Assert.Equal(2, page.GetProperty("count").GetInt32()); Assert.Single(page.GetProperty("results").EnumerateArray());
        Assert.Equal("Segunda SpA", page.GetProperty("results")[0].GetProperty("customer_business_name").GetString()); Assert.False(page.GetProperty("results")[0].TryGetProperty("items", out _)); Assert.Equal(1, page.GetProperty("results")[0].GetProperty("item_count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?currency=CLP"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?currency=USD&sale_condition=Credit30Days"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?search=Segunda"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?search=123456785"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?search=Bruno"))).GetProperty("count").GetInt32());
        Assert.Equal(0, (await JsonAsync(await seller.GetAsync("/api/admin/commercial-quotes?search=missing"))).GetProperty("count").GetInt32());
        Assert.Equal(HttpStatusCode.BadRequest, (await seller.GetAsync("/api/admin/commercial-quotes?page_size=101")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await seller.GetAsync("/api/admin/commercial-quotes?page=0&currency=EUR")).StatusCode);
    }

    [Fact]
    public async Task DetailHasOrderedPublicContractWithoutInternalOrCredentialFields()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller");
        var payload = DraftNode(); payload["items"] = new JsonArray(FreeItem("Uno", 1, 100m, 12.5m), FreeItem("Dos", 2, 20m, 0m));
        var created = await CreateAsync(seller, payload); var id = created.GetProperty("id").GetInt32();
        var response = await seller.GetAsync($"/api/admin/commercial-quotes/{id}"); var raw = await response.Content.ReadAsStringAsync(); var json = JsonDocument.Parse(raw).RootElement;
        Assert.Equal(HttpStatusCode.OK, response.StatusCode); Assert.Equal(1, json.GetProperty("items")[0].GetProperty("position").GetInt32()); Assert.Equal(2, json.GetProperty("items")[1].GetProperty("position").GetInt32());
        Assert.Equal(JsonValueKind.Null, json.GetProperty("customer_profile_id").ValueKind); Assert.True(json.TryGetProperty("created_at", out _)); Assert.True(json.TryGetProperty("updated_at", out _));
        foreach (var forbidden in new[] { "folio", "password", "hash", "token", "responsible_seller", "commercial_quote", "normalized_rut" }) Assert.DoesNotContain(forbidden, raw, StringComparison.OrdinalIgnoreCase);
        Assert.Equal(HttpStatusCode.NotFound, (await seller.GetAsync("/api/admin/commercial-quotes/999999")).StatusCode);
    }

    [Fact]
    public async Task UpdateReplacesEditableDataButPreservesOwnershipCreatedAtAndReferencedEntities()
    {
        await using var factory = new QuoteApiFactory(); var (profileId, productId) = await factory.AddCatalogDataAsync(); using var seller = await factory.AuthorizedClientAsync("seller");
        var originalPayload = DraftNode(); originalPayload["items"] = new JsonArray(new JsonObject { ["source"] = "Catalog", ["product_id"] = productId, ["quantity"] = 1, ["unit_net_amount"] = 100 });
        var original = await CreateAsync(seller, originalPayload); var id = original.GetProperty("id").GetInt32(); var createdAt = original.GetProperty("created_at").GetDateTimeOffset(); await Task.Delay(20);
        var update = DraftNode("Actualizada SpA", "USD", "Credit30Days", "Contacto Nuevo"); update["customer_profile_id"] = profileId; update["validity_days"] = 30; update["detailed_description"] = "Nueva";
        update["seller_user_id"] = 999; update["seller_code"] = "FORGED"; update["status"] = "Issued"; update["tax_rate_percent"] = 1;
        update["net_amount"] = 1; update["tax_amount"] = 1; update["total_amount"] = 1; update["created_at"] = "2000-01-01T00:00:00Z"; update["updated_at"] = "2000-01-01T00:00:00Z";
        var replacement = FreeItem("Repuesto", 2, 10.25m, 0m); replacement["position"] = 99; replacement["final_unit_net_amount"] = 1; replacement["line_net_amount"] = 1; update["items"] = new JsonArray(replacement);
        var response = await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", update); Assert.Equal(HttpStatusCode.OK, response.StatusCode); var json = await JsonAsync(response);
        Assert.Equal("Actualizada SpA", json.GetProperty("customer_business_name").GetString()); Assert.Equal("USD", json.GetProperty("currency").GetString()); Assert.Equal("Credit30Days", json.GetProperty("sale_condition").GetString()); Assert.Equal(30, json.GetProperty("validity_days").GetInt32());
        Assert.Equal("Draft", json.GetProperty("status").GetString()); Assert.Equal("VEN-0001", json.GetProperty("seller_code").GetString()); Assert.Equal(createdAt, json.GetProperty("created_at").GetDateTimeOffset()); Assert.True(json.GetProperty("updated_at").GetDateTimeOffset() > createdAt);
        Assert.Equal(20.50m, json.GetProperty("net_amount").GetDecimal()); Assert.Equal(3.90m, json.GetProperty("tax_amount").GetDecimal()); Assert.Equal(24.40m, json.GetProperty("total_amount").GetDecimal());
        Assert.Equal(19m, json.GetProperty("tax_rate_percent").GetDecimal()); Assert.Equal(1, json.GetProperty("items")[0].GetProperty("position").GetInt32()); Assert.Equal(10.25m, json.GetProperty("items")[0].GetProperty("final_unit_net_amount").GetDecimal());
        Assert.Equal("Perfil original", await factory.ProfileBusinessNameAsync(profileId)); Assert.Equal("Producto real", await factory.ProductNameAsync(productId));
        update["customer_profile_id"] = null; update["items"] = new JsonArray(); Assert.Equal(HttpStatusCode.OK, (await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", update)).StatusCode);
    }

    [Fact]
    public async Task NonDraftUpdateConflictsAndMissingProfileDoesNotAlterExistingDraft()
    {
        await using var factory = new QuoteApiFactory(); using var seller = await factory.AuthorizedClientAsync("seller"); var original = await CreateAsync(seller, DraftNode()); var id = original.GetProperty("id").GetInt32();
        await factory.SetStatusAsync(id, "Issued"); Assert.Equal(HttpStatusCode.Conflict, (await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", DraftNode())).StatusCode);
        await factory.SetStatusAsync(id, "Draft"); var invalid = DraftNode("Changed"); invalid["customer_profile_id"] = 999999; Assert.Equal(HttpStatusCode.BadRequest, (await seller.PutAsJsonAsync($"/api/admin/commercial-quotes/{id}", invalid)).StatusCode);
        var unchanged = await JsonAsync(await seller.GetAsync($"/api/admin/commercial-quotes/{id}")); Assert.Equal("Primera Ltda", unchanged.GetProperty("customer_business_name").GetString());
    }

    private static JsonObject DraftNode(string businessName = "Primera Ltda", string currency = "CLP", string saleCondition = "Cash", string contact = "Ana Uno") => new()
    {
        ["customer_profile_id"] = null, ["customer_business_name"] = businessName, ["customer_rut"] = "12.345.678-5", ["customer_business_activity"] = "Servicios industriales",
        ["customer_address"] = "Calle Uno 123", ["customer_phone"] = "+56 9 1234 5678", ["customer_city_or_commune"] = "Santiago", ["customer_contact_name"] = contact,
        ["customer_email"] = null, ["currency"] = currency, ["sale_condition"] = saleCondition, ["validity_days"] = 15, ["detailed_description"] = null, ["items"] = new JsonArray(FreeItem())
    };
    private static JsonObject FreeItem(string name = "Servicio", int quantity = 1, decimal amount = 100m, decimal discount = 0m) => new() { ["source"] = "FreeText", ["product_id"] = null, ["product_name"] = name, ["quantity"] = quantity, ["unit_net_amount"] = amount, ["discount_percent"] = discount };
    private static async Task<JsonElement> CreateAsync(HttpClient client, JsonObject payload) { using var response = await client.PostAsJsonAsync("/api/admin/commercial-quotes", payload); Assert.Equal(HttpStatusCode.Created, response.StatusCode); return await JsonAsync(response); }

    private static object ValidDraft(string currency = "CLP", string rut = "12.345.678-5", int? profileId = null, object[]? items = null) => new
    {
        customer_profile_id = profileId, customer_business_name = "ACME enviada", customer_rut = rut, customer_business_activity = "Servicios industriales",
        customer_address = "Calle Uno 123", customer_phone = "+56 9 1234 5678", customer_city_or_commune = "Santiago", customer_contact_name = "Ana Pérez",
        customer_email = (string?)null, currency, sale_condition = "Cash", detailed_description = (string?)null, items = items ?? []
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
        public async Task SetStatusAsync(int id, string status) { using var scope = Services.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>(); (await db.CommercialQuotes.FindAsync(id))!.Status = status; await db.SaveChangesAsync(); }
        public async Task<string> ProfileBusinessNameAsync(int id) { using var scope = Services.CreateScope(); return (await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().CustomerProfiles.FindAsync(id))!.BusinessName; }
        public async Task<string> ProductNameAsync(int id) { using var scope = Services.CreateScope(); return (await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().Products.FindAsync(id))!.Name; }
    }
}
