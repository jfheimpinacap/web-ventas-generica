using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
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

public sealed class AdminCustomerEndpointTests
{
    private const string Password = "SyntheticPassword123!";

    [Fact]
    public async Task EveryEndpointRequiresAuthentication()
    {
        await using var factory = new CustomerApiFactory();
        using var client = factory.CreateClient();
        foreach (var request in CustomerRequests())
        {
            using (request)
            using (var response = await client.SendAsync(request))
                Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        }
    }

    [Theory]
    [InlineData("seller")]
    [InlineData("support")]
    public async Task SellerAndSupportAdminCanCreateSearchReadAndUpdate(string username)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, username);
        var created = await PostAsync(client, Payload(Rut(10000001), businessName: "Áridos Sintéticos SpA"));
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        var createdJson = await JsonAsync(created);
        var id = createdJson.GetProperty("id").GetInt32();

        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/admin/customers?search=aridos&page=1&page_size=20")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync($"/api/admin/customers/{id}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.PutAsJsonAsync($"/api/admin/customers/{id}", Payload(Rut(10000001), businessName: "Áridos Editados SpA"))).StatusCode);
    }

    [Fact]
    public async Task AuthenticatedRoleWithoutPermissionGetsForbiddenForReadAndWrite()
    {
        await using var factory = new CustomerApiFactory();
        await factory.AddUserAsync("viewer", "catalog_viewer");
        using var client = await AuthorizedClientAsync(factory, "viewer");
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync("/api/admin/customers?search=algo")).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await PostAsync(client, Payload(Rut(10000002)))).StatusCode);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public async Task OptionalEmailIsReturnedAndStoredAsNull(string? email)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var response = await PostAsync(client, Payload(Rut(10000003), email: email));
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var json = await JsonAsync(response);
        Assert.Equal(JsonValueKind.Null, json.GetProperty("email").ValueKind);
        using var scope = factory.Services.CreateScope();
        Assert.Null((await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().CustomerProfiles.SingleAsync()).Email);
    }

    [Theory]
    [InlineData("business_name")]
    [InlineData("rut")]
    [InlineData("business_activity")]
    [InlineData("address")]
    [InlineData("phone")]
    [InlineData("city_or_commune")]
    [InlineData("contact_name")]
    public async Task EveryRequiredFieldRejectsBlankContent(string field)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var payload = Payload(Rut(10000004));
        payload[field] = "   ";
        var response = await PostAsync(client, payload);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Contains(field, await response.Content.ReadAsStringAsync(), StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData("invalid-email", "12345678-5", "email")]
    [InlineData("contact@example.test", "12345678-4", "rut")]
    [InlineData("contact@example.test", "not-a-rut", "rut")]
    public async Task InvalidEmailAndRutAreRejected(string email, string rut, string expectedError)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var response = await PostAsync(client, Payload(rut, email: email));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Contains(expectedError, await response.Content.ReadAsStringAsync(), StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData("12.345.678-5")]
    [InlineData("123456785")]
    public async Task EquivalentRutFormatsAreCanonicalAndDuplicate(string formattedRut)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var first = await PostAsync(client, Payload(formattedRut));
        Assert.Equal(HttpStatusCode.Created, first.StatusCode);
        Assert.Equal("12345678-5", (await JsonAsync(first)).GetProperty("rut").GetString());
        var duplicate = await PostAsync(client, Payload("12345678-5", businessName: "Cliente duplicado"));
        Assert.Equal(HttpStatusCode.Conflict, duplicate.StatusCode);
        var body = await duplicate.Content.ReadAsStringAsync();
        Assert.DoesNotContain("IX_CustomerProfiles", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("SqlException", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task CreationPersistsCanonicalVisibleAndAuditedValuesWithoutOverposting()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var payload = Payload("12.345.678-5", businessName: "  Áridos   Ñuble SpA  ", email: " contacto@example.test ");
        payload["normalized_rut"] = "FORGED";
        payload["normalized_business_name"] = "FORGED";
        payload["created_at"] = "2000-01-01T00:00:00Z";
        payload["updated_at"] = "2000-01-01T00:00:00Z";
        payload["created_by_id"] = 999999;
        payload["updated_by_id"] = 999999;
        var response = await PostAsync(client, payload);
        var json = await JsonAsync(response);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.Equal("Áridos Ñuble SpA", json.GetProperty("business_name").GetString());
        Assert.Equal("12345678-5", json.GetProperty("rut").GetString());
        Assert.Equal("contacto@example.test", json.GetProperty("email").GetString());
        Assert.NotEqual(DateTimeOffset.Parse("2000-01-01T00:00:00Z"), json.GetProperty("created_at").GetDateTimeOffset());
        Assert.Equal(TimeSpan.Zero, json.GetProperty("created_at").GetDateTimeOffset().Offset);
        AssertSafeContract(json);

        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var stored = await db.CustomerProfiles.SingleAsync();
        var seller = await db.AppUsers.SingleAsync(user => user.Username == "seller");
        Assert.Equal("12345678-5", stored.NormalizedRut);
        Assert.Equal("ARIDOS NUBLE SPA", stored.NormalizedBusinessName);
        Assert.Equal(seller.Id, stored.CreatedById);
        Assert.Equal(seller.Id, stored.UpdatedById);
    }

    [Fact]
    public async Task SearchSupportsBusinessNameRutNoResultsStableOrderingAndPagination()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "support");
        var alpha1 = await CreateAsync(client, Payload(Rut(10000010), businessName: "Álamo Comercial"));
        var alpha2 = await CreateAsync(client, Payload(Rut(10000011), businessName: "Alamo Comercial"));
        var beta = await CreateAsync(client, Payload(Rut(10000012), businessName: "Beta Sintética"));

        foreach (var term in new[] { "Álamo Comercial", "alamo", "ALAMO", Dotted(Rut(10000010)), Rut(10000010), Rut(10000010).Replace("-", "") })
        {
            var result = await SearchAsync(client, term);
            Assert.Contains(result.GetProperty("results").EnumerateArray(), item => item.GetProperty("id").GetInt32() == alpha1);
            Assert.DoesNotContain(result.GetProperty("results").EnumerateArray(), item => item.GetProperty("id").GetInt32() == beta);
            AssertSafeContract(result.GetProperty("results")[0]);
        }

        var page1 = await SearchAsync(client, "alamo", pageSize: 1);
        var page2 = await SearchAsync(client, "alamo", page: 2, pageSize: 1);
        Assert.Equal(2, page1.GetProperty("count").GetInt32());
        Assert.Equal(1, page1.GetProperty("page_size").GetInt32());
        Assert.Equal(alpha1, page1.GetProperty("results")[0].GetProperty("id").GetInt32());
        Assert.Equal(alpha2, page2.GetProperty("results")[0].GetProperty("id").GetInt32());

        var none = await client.GetAsync("/api/admin/customers?search=inexistente");
        Assert.Equal(HttpStatusCode.OK, none.StatusCode);
        Assert.Empty((await JsonAsync(none)).GetProperty("results").EnumerateArray());
    }

    [Theory]
    [InlineData("/api/admin/customers?search=a")]
    [InlineData("/api/admin/customers?search=valid&page_size=101")]
    public async Task SearchRejectsUnsafeLimitsAndDoesNotEnumerateAll(string path)
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        await CreateAsync(client, Payload(Rut(10000020)));
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync(path)).StatusCode);
    }

    [Fact]
    public async Task ListingFiltersStatusAndLifecycleActionsAreIdempotent()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "support");
        var id = await CreateAsync(client, Payload(Rut(10000021)));

        foreach (var path in new[] { $"/api/admin/customers/{id}/deactivate", $"/api/admin/customers/{id}/deactivate" })
        {
            var response = await client.PostAsync(path, null);
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.False((await JsonAsync(response)).GetProperty("is_active").GetBoolean());
        }
        Assert.Equal(0, (await JsonAsync(await client.GetAsync("/api/admin/customers?status=active"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await client.GetAsync("/api/admin/customers?status=inactive"))).GetProperty("count").GetInt32());
        Assert.Equal(1, (await JsonAsync(await client.GetAsync("/api/admin/customers?status=all"))).GetProperty("count").GetInt32());

        foreach (var path in new[] { $"/api/admin/customers/{id}/reactivate", $"/api/admin/customers/{id}/reactivate" })
        {
            var response = await client.PostAsync(path, null);
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.True((await JsonAsync(response)).GetProperty("is_active").GetBoolean());
        }
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/admin/customers?status=deleted")).StatusCode);
        Assert.Equal(HttpStatusCode.MethodNotAllowed, (await client.DeleteAsync($"/api/admin/customers/{id}")).StatusCode);
    }

    [Fact]
    public async Task SearchRejectsTermOverMaximum()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync($"/api/admin/customers?search={new string('a', 201)}")).StatusCode);
    }

    [Fact]
    public async Task DetailReturnsCompleteSafeDtoAndMissingOrInvalidIdReturnsNotFound()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "seller");
        var id = await CreateAsync(client, Payload(Rut(10000030), email: null));
        var response = await client.GetAsync($"/api/admin/customers/{id}");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var json = await JsonAsync(response);
        foreach (var property in new[] { "id", "business_name", "rut", "business_activity", "address", "phone", "city_or_commune", "contact_name", "email", "created_at", "updated_at" })
            Assert.True(json.TryGetProperty(property, out _), $"Missing property {property}");
        Assert.Equal(JsonValueKind.Null, json.GetProperty("email").ValueKind);
        AssertSafeContract(json);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/admin/customers/999999")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/admin/customers/not-an-id")).StatusCode);
    }

    [Theory]
    [InlineData("seller")]
    [InlineData("support")]
    public async Task UpdatePersistsValuesTimestampsAuditAndIgnoresInternalFields(string username)
    {
        await using var factory = new CustomerApiFactory();
        using var creator = await AuthorizedClientAsync(factory, "seller");
        var id = await CreateAsync(creator, Payload(Rut(10000040)));
        using var scopeBefore = factory.Services.CreateScope();
        var before = await scopeBefore.ServiceProvider.GetRequiredService<JemNexusDbContext>().CustomerProfiles.AsNoTracking().SingleAsync();
        await Task.Delay(20);
        using var updater = await AuthorizedClientAsync(factory, username);
        var payload = Payload(Dotted(Rut(10000041)), businessName: "Cliente Actualizado", email: " updated@example.test ");
        payload["created_at"] = "2000-01-01T00:00:00Z";
        payload["updated_at"] = "2000-01-01T00:00:00Z";
        payload["normalized_rut"] = "FORGED";
        payload["normalized_business_name"] = "FORGED";
        payload["updated_by_id"] = 999999;
        var response = await updater.PutAsJsonAsync($"/api/admin/customers/{id}", payload);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var json = await JsonAsync(response);
        Assert.Equal(id, json.GetProperty("id").GetInt32());
        Assert.Equal(Rut(10000041), json.GetProperty("rut").GetString());
        Assert.Equal("updated@example.test", json.GetProperty("email").GetString());
        AssertSafeContract(json);

        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var stored = await db.CustomerProfiles.SingleAsync();
        var actor = await db.AppUsers.SingleAsync(user => user.Username == username);
        Assert.Equal(before.CreatedAt, stored.CreatedAt);
        Assert.True(stored.UpdatedAt > before.UpdatedAt);
        Assert.Equal(actor.Id, stored.UpdatedById);
    }

    [Fact]
    public async Task UpdateHandlesNotFoundValidationDuplicateSameRutAndNullableEmail()
    {
        await using var factory = new CustomerApiFactory();
        using var client = await AuthorizedClientAsync(factory, "support");
        var firstRut = Rut(10000050);
        var first = await CreateAsync(client, Payload(firstRut));
        var secondRut = Rut(10000051);
        var second = await CreateAsync(client, Payload(secondRut, businessName: "Segundo Cliente"));
        Assert.Equal(HttpStatusCode.NotFound, (await client.PutAsJsonAsync("/api/admin/customers/999999", Payload(Rut(10000052)))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PutAsJsonAsync($"/api/admin/customers/{first}", Payload("invalid"))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PutAsJsonAsync($"/api/admin/customers/{first}", Payload(firstRut, email: "invalid"))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PutAsJsonAsync($"/api/admin/customers/{first}", Payload(firstRut, businessName: " "))).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict, (await client.PutAsJsonAsync($"/api/admin/customers/{first}", Payload(secondRut))).StatusCode);

        var same = await client.PutAsJsonAsync($"/api/admin/customers/{first}", Payload(Dotted(firstRut), email: " "));
        Assert.Equal(HttpStatusCode.OK, same.StatusCode);
        Assert.Equal(firstRut, (await JsonAsync(same)).GetProperty("rut").GetString());
        Assert.Equal(JsonValueKind.Null, (await JsonAsync(same)).GetProperty("email").ValueKind);
        Assert.Equal(second, (await JsonAsync(await client.GetAsync($"/api/admin/customers/{second}"))).GetProperty("id").GetInt32());
    }

    private static IEnumerable<HttpRequestMessage> CustomerRequests()
    {
        yield return new(HttpMethod.Get, "/api/admin/customers?search=test");
        yield return new(HttpMethod.Get, "/api/admin/customers/1");
        yield return JsonRequest(HttpMethod.Post, "/api/admin/customers");
        yield return JsonRequest(HttpMethod.Put, "/api/admin/customers/1");
        yield return JsonRequest(HttpMethod.Post, "/api/admin/customers/1/deactivate");
        yield return JsonRequest(HttpMethod.Post, "/api/admin/customers/1/reactivate");
    }

    private static HttpRequestMessage JsonRequest(HttpMethod method, string path) => new(method, path) { Content = new StringContent("{}", Encoding.UTF8, "application/json") };
    private static Task<HttpResponseMessage> PostAsync(HttpClient client, Dictionary<string, object?> payload) => client.PostAsJsonAsync("/api/admin/customers", payload);
    private static async Task<int> CreateAsync(HttpClient client, Dictionary<string, object?> payload) => (await JsonAsync(await PostAsync(client, payload))).GetProperty("id").GetInt32();
    private static async Task<JsonElement> SearchAsync(HttpClient client, string term, int page = 1, int pageSize = 20) => await JsonAsync(await client.GetAsync($"/api/admin/customers?search={Uri.EscapeDataString(term)}&page={page}&page_size={pageSize}"));
    private static async Task<JsonElement> JsonAsync(HttpResponseMessage response) => JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.Clone();

    private static Dictionary<string, object?> Payload(string rut, string businessName = "Empresa Sintética SpA", string? email = "contact@example.test") => new()
    {
        ["business_name"] = businessName, ["rut"] = rut, ["business_activity"] = "Servicios de prueba", ["address"] = "Calle de Pruebas 123",
        ["phone"] = "+56 2 2000 0000", ["city_or_commune"] = "Comuna Sintética", ["contact_name"] = "Contacto de Prueba", ["email"] = email
    };

    private static string Rut(int body)
    {
        var digits = body.ToString(); var sum = 0; var multiplier = 2;
        for (var index = digits.Length - 1; index >= 0; index--) { sum += (digits[index] - '0') * multiplier; multiplier = multiplier == 7 ? 2 : multiplier + 1; }
        var remainder = 11 - sum % 11; var verifier = remainder == 11 ? "0" : remainder == 10 ? "K" : remainder.ToString();
        return $"{digits}-{verifier}";
    }

    private static string Dotted(string rut) => $"{rut[..2]}.{rut[2..5]}.{rut[5..]}";

    private static void AssertSafeContract(JsonElement value)
    {
        var json = value.GetRawText();
        Assert.True(value.TryGetProperty("is_active", out _));
        foreach (var forbidden in new[] { "normalized_rut", "normalized_business_name", "created_by_user_id", "updated_by_user_id", "created_by", "updated_by", "password", "password_hash", "token" })
            Assert.DoesNotContain(forbidden, json, StringComparison.OrdinalIgnoreCase);
    }

    private static async Task<HttpClient> AuthorizedClientAsync(CustomerApiFactory factory, string username)
    {
        var client = factory.CreateClient();
        var response = await client.PostAsJsonAsync("/api/auth/login", new { username, password = Password });
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var login = await JsonAsync(response);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.GetProperty("access").GetString());
        return client;
    }

    public sealed class CustomerApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("AdminCustomerEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Issuer"] = "Customer API Test", ["Jwt:Audience"] = "Customer Frontend Test", ["Jwt:Secret"] = "customer-api-test-secret-not-for-production-32chars",
                ["SeedUsers:SellerUsername"] = "seller", ["SeedUsers:SellerPassword"] = Password, ["SeedUsers:SellerEmail"] = "seller@example.test",
                ["SeedUsers:SupportUsername"] = "support", ["SeedUsers:SupportPassword"] = Password, ["SeedUsers:SupportEmail"] = "support@example.test"
            }));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<ISellerCodeGenerator>();
                services.AddSingleton<ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.AddDbContext<JemNexusDbContext>(options => InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }

        public async Task AddUserAsync(string username, string role)
        {
            using var scope = Services.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var hasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
            var user = new AppUser { Username = username, Role = role, IsActive = true, IsStaff = true };
            user.PasswordHash = hasher.HashPassword(user, Password);
            db.AppUsers.Add(user);
            await db.SaveChangesAsync();
        }
    }
}
