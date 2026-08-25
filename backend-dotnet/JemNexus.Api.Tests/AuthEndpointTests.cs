using System.IdentityModel.Tokens.Jwt;
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

public sealed class AuthEndpointTests : IClassFixture<AuthEndpointTests.AuthApiFactory>
{
    private const string TestPassword = "DummyPassword123!";
    private readonly AuthApiFactory _factory;

    public AuthEndpointTests(AuthApiFactory factory)
    {
        _factory = factory;
    }

    [Theory]
    [InlineData("/api/auth/login")]
    [InlineData("/api/auth/login/")]
    public async Task LoginWithValidCredentialsReturnsAccessRefreshAndUser(string loginPath)
    {
        using var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var payload = await ReadSuccessfulJsonAsync<LoginPayload>(response);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
        Assert.False(string.IsNullOrWhiteSpace(payload.Refresh));
        Assert.Equal("demo", payload.User.Username);
        Assert.Equal(AppRoles.Seller, payload.User.Role);
        Assert.True(payload.User.IsStaff);
        Assert.Matches("^VEN-[0-9]{4,}$", payload.User.SellerCode!);
    }

    [Theory]
    [InlineData("/api/auth/login")]
    [InlineData("/api/auth/login/")]
    public async Task LoginWithInvalidCredentialsReturnsUnauthorized(string loginPath)
    {
        using var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = "wrong-password" });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/auth/me")]
    [InlineData("/api/auth/me/")]
    public async Task MeWithoutBearerTokenReturnsUnauthorized(string mePath)
    {
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(mePath);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/auth/login", "/api/auth/me")]
    [InlineData("/api/auth/login/", "/api/auth/me/")]
    public async Task MeWithBearerTokenReturnsCurrentUser(string loginPath, string mePath)
    {
        using var client = _factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(loginResponse);

        Assert.False(string.IsNullOrWhiteSpace(login.Access));
        var jwt = new JwtSecurityTokenHandler().ReadJwtToken(login.Access);
        Assert.Contains(jwt.Claims, claim => claim.Type == JwtRegisteredClaimNames.Sub && !string.IsNullOrWhiteSpace(claim.Value));
        Assert.Contains(jwt.Claims, claim => claim.Type == JwtRegisteredClaimNames.UniqueName && claim.Value == "demo");
        Assert.Contains(jwt.Claims, claim => claim.Type == "pwd_ver" && !string.IsNullOrWhiteSpace(claim.Value));
        Assert.DoesNotContain(jwt.Claims, claim => claim.Type.Contains("password", StringComparison.OrdinalIgnoreCase));
        Assert.DoesNotContain(jwt.Claims, claim => claim.Value.Contains(TestPassword, StringComparison.Ordinal));

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        var response = await client.GetAsync(mePath);
        var user = await ReadSuccessfulJsonAsync<UserPayload>(response);

        Assert.NotNull(user);
        Assert.Equal("demo", user.Username);
        Assert.Equal(AppRoles.Seller, user.Role);
        Assert.Equal(login.User.SellerCode, user.SellerCode);
        Assert.DoesNotContain(jwt.Claims, claim => claim.Type.Contains("seller_code", StringComparison.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData("/api/auth/login", "/api/auth/refresh")]
    [InlineData("/api/auth/login/", "/api/auth/refresh/")]
    public async Task RefreshWithPersistedRefreshTokenReturnsNewAccessToken(string loginPath, string refreshPath)
    {
        using var client = _factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(loginResponse);

        var response = await client.PostAsJsonAsync(refreshPath, new { refresh = login.Refresh });
        var payload = await ReadSuccessfulJsonAsync<RefreshPayload>(response);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
        Assert.False(string.IsNullOrWhiteSpace(payload.Refresh));
        Assert.NotEqual(login.Refresh, payload.Refresh);
    }

    [Fact]
    public async Task ReusingRotatedRefreshTokenRevokesItsSuccessor()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);
        var rotated = await RefreshAsync(client, login.Refresh);

        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, login.Refresh)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, rotated.Refresh)).StatusCode);
    }

    [Fact]
    public async Task SuccessiveRefreshesReturnDistinctTokens()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);
        var first = await RefreshAsync(client, login.Refresh);
        var second = await RefreshAsync(client, first.Refresh);

        Assert.NotEqual(login.Refresh, first.Refresh);
        Assert.NotEqual(first.Refresh, second.Refresh);
    }

    [Fact]
    public async Task RefreshTokenReuseOnlyRevokesCompromisedFamily()
    {
        using var client = _factory.CreateClient();
        var familyA = await LoginAsync(client);
        var familyB = await LoginAsync(client);
        var successorA = await RefreshAsync(client, familyA.Refresh);

        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, familyA.Refresh)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, successorA.Refresh)).StatusCode);
        var successorB = await RefreshAsync(client, familyB.Refresh);
        Assert.False(string.IsNullOrWhiteSpace(successorB.Refresh));
    }

    [Fact]
    public async Task ConcurrentRefreshAllowsOneWinnerAndRevokesItsSuccessor()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);

        var responses = await Task.WhenAll(PostRefreshAsync(client, login.Refresh), PostRefreshAsync(client, login.Refresh));
        Assert.Equal(1, responses.Count(response => response.IsSuccessStatusCode));
        Assert.Equal(1, responses.Count(response => response.StatusCode == HttpStatusCode.Unauthorized));
        var winner = await ReadSuccessfulJsonAsync<RefreshPayload>(responses.Single(response => response.IsSuccessStatusCode));
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, winner.Refresh)).StatusCode);
    }

    [Fact]
    public async Task RotationPersistsHashesAndKeepsLoginFamiliesIndependent()
    {
        using var client = _factory.CreateClient();
        var familyA = await LoginAsync(client);
        var familyB = await LoginAsync(client);
        var successorA = await RefreshAsync(client, familyA.Refresh);

        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var tokens = await db.AppRefreshTokens.AsNoTracking().ToListAsync();
        var tokenService = scope.ServiceProvider.GetRequiredService<IJwtTokenService>();
        var user = await db.AppUsers.AsNoTracking().SingleAsync(candidate => candidate.Username == "demo");
        var originalHash = tokenService.HashRefreshToken(familyA.Refresh);
        var successorHash = tokenService.HashRefreshToken(successorA.Refresh);
        var familyBHash = tokenService.HashRefreshToken(familyB.Refresh);
        var original = tokens.Single(token => token.TokenHash == originalHash);
        var successor = tokens.Single(token => token.TokenHash == successorHash);
        var otherFamily = tokens.Single(token => token.TokenHash == familyBHash);

        Assert.NotNull(original.RevokedAt);
        Assert.Equal(successorHash, original.ReplacedByTokenHash);
        Assert.Equal(original.FamilyId, successor.FamilyId);
        Assert.NotEqual(original.FamilyId, otherFamily.FamilyId);
        Assert.DoesNotContain(tokens, token => token.TokenHash == successorA.Refresh);
        Assert.Single(tokens, token => token.FamilyId == original.FamilyId && token.RevokedAt == null);
        Assert.False(string.IsNullOrWhiteSpace(original.PasswordVersion));
        Assert.Equal(original.PasswordVersion, successor.PasswordVersion);
        Assert.Equal(tokenService.GetPasswordVersion(user), original.PasswordVersion);
    }

    [Theory]
    [InlineData("/api/auth/logout")]
    [InlineData("/api/auth/logout/")]
    public async Task LogoutRevokesCurrentFamily(string logoutPath)
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);

        var logout = await client.PostAsJsonAsync(logoutPath, new { refresh = login.Refresh });

        Assert.Equal(HttpStatusCode.NoContent, logout.StatusCode);
        Assert.Empty(await logout.Content.ReadAsByteArrayAsync());
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, login.Refresh)).StatusCode);
    }

    [Fact]
    public async Task LogoutIsIdempotentAndDoesNotEnumerateTokens()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);

        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = "unknown" })).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = "" })).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = login.Refresh })).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = login.Refresh })).StatusCode);
    }

    [Fact]
    public async Task LogoutOnlyRevokesSelectedLoginFamily()
    {
        using var client = _factory.CreateClient();
        var familyA = await LoginAsync(client);
        var familyB = await LoginAsync(client);

        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = familyA.Refresh })).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, familyA.Refresh)).StatusCode);
        Assert.True((await PostRefreshAsync(client, familyB.Refresh)).IsSuccessStatusCode);
    }

    [Fact]
    public async Task LogoutWithRotatedTokenRevokesSuccessor()
    {
        using var client = _factory.CreateClient();
        var original = await LoginAsync(client);
        var successor = await RefreshAsync(client, original.Refresh);

        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsJsonAsync("/api/auth/logout", new { refresh = original.Refresh })).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, successor.Refresh)).StatusCode);
    }

    [Fact]
    public async Task ConcurrentRefreshAndLogoutLeaveFamilyWithoutUsableSuccessor()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);
        using var scope = _factory.Services.CreateScope();
        var service = scope.ServiceProvider.GetRequiredService<IJwtTokenService>();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var familyId = (await db.AppRefreshTokens.AsNoTracking()
            .SingleAsync(token => token.TokenHash == service.HashRefreshToken(login.Refresh))).FamilyId;

        var refreshTask = PostRefreshAsync(client, login.Refresh);
        var logoutTask = client.PostAsJsonAsync("/api/auth/logout", new { refresh = login.Refresh });
        await Task.WhenAll(refreshTask, logoutTask);

        Assert.Equal(HttpStatusCode.NoContent, logoutTask.Result.StatusCode);
        Assert.Contains(refreshTask.Result.StatusCode, new[] { HttpStatusCode.OK, HttpStatusCode.Unauthorized });
        if (refreshTask.Result.StatusCode == HttpStatusCode.OK)
        {
            var successor = await ReadSuccessfulJsonAsync<RefreshPayload>(refreshTask.Result);
            Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, successor.Refresh)).StatusCode);
        }

        db.ChangeTracker.Clear();
        Assert.False(await db.AppRefreshTokens.AnyAsync(token => token.FamilyId == familyId && token.RevokedAt == null));
    }

    [Fact]
    public async Task HistoricalTokenWithoutPasswordVersionIsRejectedAndFamilyRevoked()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var service = scope.ServiceProvider.GetRequiredService<IJwtTokenService>();
            var token = await db.AppRefreshTokens.SingleAsync(candidate => candidate.TokenHash == service.HashRefreshToken(login.Refresh));
            token.PasswordVersion = null;
            await db.SaveChangesAsync();
        }

        Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, login.Refresh)).StatusCode);
        using var verificationScope = _factory.Services.CreateScope();
        var verificationDb = verificationScope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var active = await verificationDb.AppRefreshTokens.CountAsync(token => token.PasswordVersion == null && token.RevokedAt == null);
        Assert.Equal(0, active);
    }

    [Fact]
    public async Task DirectPasswordHashChangeRejectsRefreshAndRevokesFamily()
    {
        using var client = _factory.CreateClient();
        var login = await LoginAsync(client);
        string originalHash;
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var user = await db.AppUsers.SingleAsync(candidate => candidate.Username == "demo");
            originalHash = user.PasswordHash;
            user.PasswordHash = $"externally-changed-{Guid.NewGuid():N}";
            await db.SaveChangesAsync();
        }

        try
        {
            Assert.Equal(HttpStatusCode.Unauthorized, (await PostRefreshAsync(client, login.Refresh)).StatusCode);
        }
        finally
        {
            using var scope = _factory.Services.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var user = await db.AppUsers.SingleAsync(candidate => candidate.Username == "demo");
            user.PasswordHash = originalHash;
            await db.SaveChangesAsync();
        }
    }

    [Fact]
    public async Task LoginWorksWithUserCreatedByStartupSeed()
    {
        using var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/auth/login", new { username = "demo", password = TestPassword });
        var payload = await ReadSuccessfulJsonAsync<LoginPayload>(response);

        Assert.Equal("demo", payload.User.Username);
        Assert.Equal(AppRoles.Seller, payload.User.Role);
    }

    [Fact]
    public async Task SupportLoginAndMeReturnNullSellerCode()
    {
        using var client = _factory.CreateClient();
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(
            await client.PostAsJsonAsync("/api/auth/login", new { username = "support", password = TestPassword }));
        Assert.Null(login.User.SellerCode);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        var me = await ReadSuccessfulJsonAsync<UserPayload>(await client.GetAsync("/api/auth/me"));
        Assert.Null(me.SellerCode);
        Assert.True(JsonDocument.Parse(await (await client.GetAsync("/api/auth/me")).Content.ReadAsStringAsync()).RootElement.TryGetProperty("phone", out _));
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

    private static async Task<T> ReadSuccessfulJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");

        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response body for {typeof(T).Name}. Status: {response.StatusCode}, Body: {body}");

        return payload!;
    }

    private static async Task<LoginPayload> LoginAsync(HttpClient client) =>
        await ReadSuccessfulJsonAsync<LoginPayload>(
            await client.PostAsJsonAsync("/api/auth/login", new { username = "demo", password = TestPassword }));

    private static Task<HttpResponseMessage> PostRefreshAsync(HttpClient client, string refresh) =>
        client.PostAsJsonAsync("/api/auth/refresh", new { refresh });

    private static async Task<RefreshPayload> RefreshAsync(HttpClient client, string refresh) =>
        await ReadSuccessfulJsonAsync<RefreshPayload>(await PostRefreshAsync(client, refresh));

    public sealed class AuthApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("AuthEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

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
                services.AddDbContext<JemNexusDbContext>(options =>
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }
    }

    private sealed record LoginPayload(string Access, string Refresh, UserPayload User);
    private sealed record RefreshPayload(string Access, string Refresh);
    private sealed record UserPayload(int Id, string Username, [property: JsonPropertyName("seller_code")] string? SellerCode, string? Email, string? Phone, string Role, [property: JsonPropertyName("is_staff")] bool IsStaff, [property: JsonPropertyName("is_superuser")] bool IsSuperuser);
}
