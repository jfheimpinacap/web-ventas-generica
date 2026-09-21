using System.IdentityModel.Tokens.Jwt;
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

public sealed class AdminUserEndpointTests
{
    private const string Password = "SecurePassword123!";
    private const string NewPassword = "DifferentPassword456!";

    [Fact]
    public async Task EveryEndpointRequiresAuthenticationAndRejectsSeller()
    {
        await using var factory = new AdminApiFactory();
        using var anonymous = factory.CreateClient();
        var requests = CreateAllRequests();
        foreach (var request in requests)
        {
            using (request)
            using (var response = await anonymous.SendAsync(request))
                Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        }

        using var seller = factory.CreateClient();
        await AuthenticateAsync(seller, "seller", Password);
        foreach (var request in CreateAllRequests())
        {
            using (request)
            using (var response = await seller.SendAsync(request))
                Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
        }
    }

    [Fact]
    public async Task SupportAdminListsBothRolesSearchesFiltersAndOmitsSecrets()
    {
        await using var factory = new AdminApiFactory();
        await AddSellerAsync(factory, "inactive.one", "find-email@example.test", "Nombre Buscable", false);
        using var client = factory.CreateClient();
        await AuthenticateAsync(client, "support", Password);

        foreach (var search in new[] { "inactive.one", "find-email", "Buscable" })
        {
            var response = await client.GetAsync($"/api/admin/users?search={Uri.EscapeDataString(search)}");
            var body = await response.Content.ReadAsStringAsync();
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("inactive.one", body);
            Assert.DoesNotContain("password", body, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("refresh", body, StringComparison.OrdinalIgnoreCase);
        }

        var inactive = await client.GetStringAsync("/api/admin/users?is_active=false");
        Assert.Contains("inactive.one", inactive);
        Assert.DoesNotContain("\"username\":\"support\"", inactive);
        var active = await client.GetStringAsync("/api/admin/users?is_active=true");
        Assert.DoesNotContain("inactive.one", active);
        Assert.Contains("\"username\":\"support\"", active);
        Assert.Contains("\"role\":\"support_admin\"", await client.GetStringAsync("/api/admin/users?role=support_admin"));
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/api/admin/users?role=admin")).StatusCode);
    }

    [Fact]
    public async Task CreateSellerIgnoresInternalFieldsHashesPasswordAndAssignsDefaults()
    {
        await using var factory = new AdminApiFactory();
        using var client = factory.CreateClient();
        await AuthenticateAsync(client, "support", Password);
        var response = await client.PostAsJsonAsync("/api/admin/users", new
        {
            username = " new.seller ", email = " new@example.test ", full_name = " New Seller ", phone = " +56 9 1234 5678 ", password = NewPassword,
            role = AppRoles.Seller, is_staff = false, is_superuser = true, seller_code = "VEN-9999"
        });
        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.Contains("\"role\":\"seller\"", body);
        Assert.Contains("\"is_staff\":true", body);
        Assert.Contains("\"is_superuser\":false", body);
        Assert.Contains("\"seller_code\":\"VEN-", body);
        Assert.DoesNotContain("VEN-9999", body);
        Assert.DoesNotContain(NewPassword, body);

        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var stored = await db.AppUsers.SingleAsync(user => user.Username == "new.seller");
        Assert.NotEqual(NewPassword, stored.PasswordHash);
        Assert.StartsWith("AQAAAA", stored.PasswordHash);
        Assert.NotNull(stored.SellerCode);
        Assert.Equal("+56 9 1234 5678", stored.Phone);
        Assert.Contains($"\"seller_code\":\"{stored.SellerCode}\"", body);
        Assert.Equal(AppPermissions.SellerGrantable, await db.AppUserPermissions.Where(value => value.UserId == stored.Id).Select(value => value.Permission).OrderBy(value => value).ToListAsync());

        using var loginClient = factory.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await LoginAsync(loginClient, "new.seller", NewPassword)).StatusCode);
    }

    [Fact]
    public async Task SellerCodesAreUniqueSearchableAndStableAcrossUpdates()
    {
        await using var factory = new AdminApiFactory();
        using var admin = factory.CreateClient();
        await AuthenticateAsync(admin, "support", Password);

        var first = await admin.PostAsJsonAsync("/api/admin/users", new { username = "code.one", password = NewPassword });
        var second = await admin.PostAsJsonAsync("/api/admin/users", new { username = "code.two", password = NewPassword });
        var firstPayload = JsonDocument.Parse(await first.Content.ReadAsStringAsync()).RootElement;
        var secondPayload = JsonDocument.Parse(await second.Content.ReadAsStringAsync()).RootElement;
        var id = firstPayload.GetProperty("id").GetInt32();
        var code = firstPayload.GetProperty("seller_code").GetString()!;
        Assert.Matches("^VEN-[0-9]{4,}$", code);
        Assert.NotEqual(code, secondPayload.GetProperty("seller_code").GetString());

        foreach (var search in new[] { code, code.ToLowerInvariant(), code[4..] })
            Assert.Contains("code.one", await admin.GetStringAsync($"/api/admin/users?search={search}"));

        var update = await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new
        {
            username = "code.edited", email = "code@example.test", full_name = "Code Edited",
            is_active = false, password = NewPassword, seller_code = "VEN-7777"
        });
        var updated = JsonDocument.Parse(await update.Content.ReadAsStringAsync()).RootElement;
        Assert.Equal(code, updated.GetProperty("seller_code").GetString());
        var detail = JsonDocument.Parse(await admin.GetStringAsync($"/api/admin/users/{id}")).RootElement;
        Assert.Equal(code, detail.GetProperty("seller_code").GetString());
    }

    [Fact]
    public async Task DuplicateAndInvalidInputsAreRejected()
    {
        await using var factory = new AdminApiFactory();
        await AddSellerAsync(factory, "duplicate", "duplicate@example.test", null, true);
        using var client = factory.CreateClient();
        await AuthenticateAsync(client, "support", Password);

        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/admin/users", new { username = "DUPLICATE", email = "unique@example.test", password = NewPassword })).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/admin/users", new { username = "unique", email = "DUPLICATE@example.test", password = NewPassword })).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/admin/users", new { username = "bad user!", email = "valid@example.test", password = NewPassword })).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/admin/users", new { username = "valid.name", email = "not-an-email", password = NewPassword })).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/admin/users", new { username = "valid.name", email = "valid@example.test", password = "weak" })).StatusCode);
    }

    [Fact]
    public async Task UpdateWithoutPasswordPreservesLoginAndNormalizesEmptyFields()
    {
        await using var factory = new AdminApiFactory();
        var id = await AddSellerAsync(factory, "editable", "edit@example.test", "Editable", true);
        var existingSession = await ReadLoginAsync(await LoginAsync(factory.CreateClient(), "editable", Password));
        using var client = factory.CreateClient();
        await AuthenticateAsync(client, "support", Password);
        var response = await client.PatchAsJsonAsync($"/api/admin/users/{id}", new { username = "edited", email = " ", full_name = "", phone = "   ", is_active = true, password = "" });
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        using var loginClient = factory.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await LoginAsync(loginClient, "edited", Password)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await factory.CreateClient().PostAsJsonAsync("/api/auth/refresh", new { refresh = existingSession.Refresh })).StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("\"email\":null", body);
        Assert.Contains("\"full_name\":null", body);
        Assert.Contains("\"phone\":null", body);
    }

    [Fact]
    public async Task PasswordChangeImmediatelyInvalidatesOldCredentialsAndSessions()
    {
        await using var factory = new AdminApiFactory();
        var id = await AddSellerAsync(factory, "changing", null, null, true);
        using var sessionClient = factory.CreateClient();
        var oldLogin = await ReadLoginAsync(await LoginAsync(sessionClient, "changing", Password));
        var secondOldLogin = await ReadLoginAsync(await LoginAsync(factory.CreateClient(), "changing", Password));
        using var admin = factory.CreateClient();
        await AuthenticateAsync(admin, "support", Password);
        var update = await admin.PutAsJsonAsync($"/api/admin/users/{id}", new { username = "changing", email = (string?)null, full_name = (string?)null, is_active = true, password = NewPassword });
        Assert.Equal(HttpStatusCode.OK, update.StatusCode);

        Assert.Equal(HttpStatusCode.Unauthorized, (await LoginAsync(factory.CreateClient(), "changing", Password)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await LoginAsync(factory.CreateClient(), "changing", NewPassword)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await factory.CreateClient().PostAsJsonAsync("/api/auth/refresh", new { refresh = oldLogin.Refresh })).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await factory.CreateClient().PostAsJsonAsync("/api/auth/refresh", new { refresh = secondOldLogin.Refresh })).StatusCode);
        using var oldAccess = factory.CreateClient();
        oldAccess.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", oldLogin.Access);
        Assert.Equal(HttpStatusCode.Unauthorized, (await oldAccess.GetAsync("/api/auth/me")).StatusCode);
        using var secondOldAccess = factory.CreateClient();
        secondOldAccess.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", secondOldLogin.Access);
        Assert.Equal(HttpStatusCode.Unauthorized, (await secondOldAccess.GetAsync("/api/auth/me")).StatusCode);
    }

    [Fact]
    public async Task DeleteDeactivatesWithoutRemovingAndInvalidatesAllCredentials()
    {
        await using var factory = new AdminApiFactory();
        var id = await AddSellerAsync(factory, "deleting", null, null, true);
        var oldLogin = await ReadLoginAsync(await LoginAsync(factory.CreateClient(), "deleting", Password));
        using var admin = factory.CreateClient();
        await AuthenticateAsync(admin, "support", Password);
        Assert.Equal(HttpStatusCode.NoContent, (await admin.DeleteAsync($"/api/admin/users/{id}")).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await admin.DeleteAsync($"/api/admin/users/{id}")).StatusCode);

        using var scope = factory.Services.CreateScope();
        var stored = await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().AppUsers.SingleAsync(user => user.Id == id);
        Assert.False(stored.IsActive);
        Assert.Equal(HttpStatusCode.Unauthorized, (await LoginAsync(factory.CreateClient(), "deleting", Password)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await factory.CreateClient().PostAsJsonAsync("/api/auth/refresh", new { refresh = oldLogin.Refresh })).StatusCode);
        using var oldAccess = factory.CreateClient();
        oldAccess.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", oldLogin.Access);
        Assert.Equal(HttpStatusCode.Unauthorized, (await oldAccess.GetAsync("/api/auth/me")).StatusCode);
    }

    [Fact]
    public async Task ReactivationRequiresNewPasswordAndNeverRestoresOldSessions()
    {
        await using var factory = new AdminApiFactory();
        var id = await AddSellerAsync(factory, "reactivate", null, null, false);
        using var admin = factory.CreateClient();
        await AuthenticateAsync(admin, "support", Password);
        Assert.Equal(HttpStatusCode.BadRequest, (await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new { username = "reactivate", is_active = true })).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new { username = "reactivate", is_active = true, password = NewPassword })).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await LoginAsync(factory.CreateClient(), "reactivate", Password)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await LoginAsync(factory.CreateClient(), "reactivate", NewPassword)).StatusCode);
    }

    [Fact]
    public async Task CurrentSupportAdminCanBeReadAndEditedButCannotDeactivateOrDemoteItself()
    {
        await using var factory = new AdminApiFactory();
        using var admin = factory.CreateClient();
        var login = await AuthenticateAsync(admin, "support", Password);
        var adminId = new JwtSecurityTokenHandler().ReadJwtToken(login.Access).Claims.Single(claim => claim.Type == JwtRegisteredClaimNames.Sub).Value;
        Assert.Equal(HttpStatusCode.OK, (await admin.GetAsync($"/api/admin/users/{adminId}")).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict, (await admin.PatchAsJsonAsync($"/api/admin/users/{adminId}", new { is_active = false })).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict, (await admin.PatchAsJsonAsync($"/api/admin/users/{adminId}", new { role = AppRoles.Seller })).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict, (await admin.DeleteAsync($"/api/admin/users/{adminId}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await LoginAsync(factory.CreateClient(), "support", Password)).StatusCode);
    }

    [Fact]
    public async Task CatalogIsDeterministicAndSeparatesGrantableAndReservedPermissions()
    {
        await using var factory = new AdminApiFactory(); using var admin = factory.CreateClient(); await AuthenticateAsync(admin, "support", Password);
        var payload = JsonDocument.Parse(await admin.GetStringAsync("/api/admin/users/permission-catalog")).RootElement;
        Assert.Equal([AppRoles.Seller, AppRoles.SupportAdmin], payload.GetProperty("roles").EnumerateArray().Select(value => value.GetString()).ToArray());
        Assert.Equal(29, payload.GetProperty("seller_grantable").GetArrayLength());
        Assert.Equal([AppPermissions.UsersManage], payload.GetProperty("reserved").EnumerateArray().Select(value => value.GetString()).ToArray());
    }

    [Theory]
    [InlineData("unknown", "products.create")]
    [InlineData("seller", "unknown.permission")]
    [InlineData("seller", "users.manage")]
    [InlineData("seller", " Products.create")]
    public async Task InvalidRolesUnknownReservedAndNonCanonicalPermissionsAreRejected(string role, string permission)
    {
        await using var factory = new AdminApiFactory(); using var admin = factory.CreateClient(); await AuthenticateAsync(admin, "support", Password);
        Assert.Equal(HttpStatusCode.BadRequest, (await admin.PostAsJsonAsync("/api/admin/users", new { username = $"invalid{permission.Length}", password = NewPassword, role, permissions = new[] { permission } })).StatusCode);
    }

    [Fact]
    public async Task DuplicatePermissionsAreRejectedWithoutCreatingUser()
    {
        await using var factory = new AdminApiFactory(); using var admin = factory.CreateClient(); await AuthenticateAsync(admin, "support", Password);
        var response = await admin.PostAsJsonAsync("/api/admin/users", new { username = "duplicate.permissions", password = NewPassword, permissions = new[] { AppPermissions.ProductsCreate, AppPermissions.ProductsCreate } });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        using var scope = factory.Services.CreateScope();
        Assert.False(await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().AppUsers.AnyAsync(user => user.Username == "duplicate.permissions"));
    }

    [Fact]
    public async Task SellerPermissionSetsSupportOmittedSubsetEmptyAndReplacementSemantics()
    {
        await using var factory = new AdminApiFactory(); using var admin = factory.CreateClient(); await AuthenticateAsync(admin, "support", Password);
        var defaults = await admin.PostAsJsonAsync("/api/admin/users", new { username = "defaults", password = NewPassword });
        var subset = await admin.PostAsJsonAsync("/api/admin/users", new { username = "subset", password = NewPassword, permissions = new[] { AppPermissions.ProductsCreate } });
        var empty = await admin.PostAsJsonAsync("/api/admin/users", new { username = "empty", password = NewPassword, permissions = Array.Empty<string>() });
        Assert.Equal(29, JsonDocument.Parse(await defaults.Content.ReadAsStringAsync()).RootElement.GetProperty("permissions").GetArrayLength());
        Assert.Single(JsonDocument.Parse(await subset.Content.ReadAsStringAsync()).RootElement.GetProperty("permissions").EnumerateArray());
        var emptyPayload = JsonDocument.Parse(await empty.Content.ReadAsStringAsync()).RootElement; Assert.Empty(emptyPayload.GetProperty("permissions").EnumerateArray());
        var id = emptyPayload.GetProperty("id").GetInt32();
        Assert.Equal(HttpStatusCode.OK, (await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new { permissions = new[] { AppPermissions.BrandsCreate } })).StatusCode);
        Assert.Single(JsonDocument.Parse(await admin.GetStringAsync($"/api/admin/users/{id}")).RootElement.GetProperty("permissions").EnumerateArray());
    }

    [Fact]
    public async Task RoleTransitionsApplyFlagsSellerCodeAndPersistentPermissionRules()
    {
        await using var factory = new AdminApiFactory(); using var admin = factory.CreateClient(); await AuthenticateAsync(admin, "support", Password);
        var created = JsonDocument.Parse(await (await admin.PostAsJsonAsync("/api/admin/users", new { username = "transition", password = NewPassword, permissions = new[] { AppPermissions.ProductsCreate } })).Content.ReadAsStringAsync()).RootElement;
        var id = created.GetProperty("id").GetInt32();
        var promoted = JsonDocument.Parse(await (await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new { role = AppRoles.SupportAdmin, permissions = Array.Empty<string>() })).Content.ReadAsStringAsync()).RootElement;
        Assert.True(promoted.GetProperty("is_superuser").GetBoolean()); Assert.Equal(JsonValueKind.Null, promoted.GetProperty("seller_code").ValueKind); Assert.Equal(30, promoted.GetProperty("permissions").GetArrayLength());
        var demoted = JsonDocument.Parse(await (await admin.PatchAsJsonAsync($"/api/admin/users/{id}", new { role = AppRoles.Seller, permissions = Array.Empty<string>() })).Content.ReadAsStringAsync()).RootElement;
        Assert.False(demoted.GetProperty("is_superuser").GetBoolean()); Assert.StartsWith("VEN-", demoted.GetProperty("seller_code").GetString()); Assert.Empty(demoted.GetProperty("permissions").EnumerateArray());
    }

    private static IEnumerable<HttpRequestMessage> CreateAllRequests()
    {
        yield return new(HttpMethod.Get, "/api/admin/users");
        yield return new(HttpMethod.Get, "/api/admin/users/permission-catalog");
        yield return new(HttpMethod.Get, "/api/admin/users/1");
        yield return JsonRequest(HttpMethod.Post, "/api/admin/users");
        yield return JsonRequest(HttpMethod.Put, "/api/admin/users/1");
        yield return JsonRequest(HttpMethod.Patch, "/api/admin/users/1");
        yield return new(HttpMethod.Delete, "/api/admin/users/1");
    }

    private static HttpRequestMessage JsonRequest(HttpMethod method, string path) => new(method, path)
    {
        Content = new StringContent("{}", Encoding.UTF8, "application/json")
    };

    private static async Task<LoginPayload> AuthenticateAsync(HttpClient client, string username, string password)
    {
        var login = await ReadLoginAsync(await LoginAsync(client, username, password));
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        return login;
    }

    private static Task<HttpResponseMessage> LoginAsync(HttpClient client, string username, string password) =>
        client.PostAsJsonAsync("/api/auth/login", new { username, password });

    private static async Task<LoginPayload> ReadLoginAsync(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        return JsonSerializer.Deserialize<LoginPayload>(body, new JsonSerializerOptions(JsonSerializerDefaults.Web))!;
    }

    private static async Task<int> AddSellerAsync(AdminApiFactory factory, string username, string? email, string? fullName, bool active)
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var hasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var generator = scope.ServiceProvider.GetRequiredService<ISellerCodeGenerator>();
        var user = new AppUser { Username = username, SellerCode = await generator.GenerateAsync(), Email = email, FullName = fullName, IsActive = active, Role = AppRoles.Seller, IsStaff = true };
        user.PasswordHash = hasher.HashPassword(user, Password);
        db.AppUsers.Add(user);
        await db.SaveChangesAsync();
        return user.Id;
    }

    private sealed record LoginPayload(string Access, string Refresh);

    public sealed class AdminApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("AdminUserEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.GetSharedDatabaseRoot();
        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Jwt:Issuer"] = "Admin API Test", ["Jwt:Audience"] = "Admin Frontend Test",
                ["Jwt:Secret"] = "admin-api-test-secret-not-for-production-32chars",
                ["SeedUsers:SellerUsername"] = "seller", ["SeedUsers:SellerPassword"] = Password,
                ["SeedUsers:SellerEmail"] = "seller@example.test", ["SeedUsers:SupportUsername"] = "support",
                ["SeedUsers:SupportPassword"] = Password, ["SeedUsers:SupportEmail"] = "support@example.test"
            }));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<JemNexus.Api.Services.ISellerCodeGenerator>();
                services.AddSingleton<JemNexus.Api.Services.ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.AddDbContext<JemNexusDbContext>(options => InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }
    }
}
