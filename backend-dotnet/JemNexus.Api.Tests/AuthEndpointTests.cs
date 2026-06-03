using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class AuthEndpointTests
{
    [Theory]
    [InlineData("/api/auth/login")]
    [InlineData("/api/auth/login/")]
    public async Task LoginWithValidCredentialsReturnsAccessRefreshAndUser(string loginPath)
    {
        await using var factory = CreateFactory();
        await SeedTestUsersAsync(factory);
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var payload = await ReadSuccessfulJsonAsync<LoginPayload>(response);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
        Assert.False(string.IsNullOrWhiteSpace(payload.Refresh));
        Assert.Equal("demo", payload.User.Username);
        Assert.Equal(AppRoles.Seller, payload.User.Role);
        Assert.True(payload.User.IsStaff);
    }

    [Theory]
    [InlineData("/api/auth/login")]
    [InlineData("/api/auth/login/")]
    public async Task LoginWithInvalidCredentialsReturnsUnauthorized(string loginPath)
    {
        await using var factory = CreateFactory();
        await SeedTestUsersAsync(factory);
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = "wrong-password" });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/auth/me")]
    [InlineData("/api/auth/me/")]
    public async Task MeWithoutBearerTokenReturnsUnauthorized(string mePath)
    {
        await using var factory = CreateFactory();
        var client = factory.CreateClient();

        var response = await client.GetAsync(mePath);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/auth/login", "/api/auth/me")]
    [InlineData("/api/auth/login/", "/api/auth/me/")]
    public async Task MeWithBearerTokenReturnsCurrentUser(string loginPath, string mePath)
    {
        await using var factory = CreateFactory();
        await SeedTestUsersAsync(factory);
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(loginResponse);

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        var response = await client.GetAsync(mePath);
        var user = await ReadSuccessfulJsonAsync<UserPayload>(response);

        Assert.NotNull(user);
        Assert.Equal("demo", user.Username);
        Assert.Equal(AppRoles.Seller, user.Role);
    }

    [Theory]
    [InlineData("/api/auth/login", "/api/auth/refresh")]
    [InlineData("/api/auth/login/", "/api/auth/refresh/")]
    public async Task RefreshWithPersistedRefreshTokenReturnsNewAccessToken(string loginPath, string refreshPath)
    {
        await using var factory = CreateFactory();
        await SeedTestUsersAsync(factory);
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = TestPassword });
        var login = await ReadSuccessfulJsonAsync<LoginPayload>(loginResponse);

        var response = await client.PostAsJsonAsync(refreshPath, new { refresh = login.Refresh });
        var payload = await ReadSuccessfulJsonAsync<RefreshPayload>(response);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
    }

    private static WebApplicationFactory<Program> CreateFactory()
    {
        return new WebApplicationFactory<Program>()
            .WithWebHostBuilder(builder =>
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
                        options.UseInMemoryDatabase(Guid.NewGuid().ToString()));
                });
            });
    }

    private const string TestPassword = "DummyPassword123!";

    private static readonly IReadOnlyDictionary<string, string?> TestConfiguration = new Dictionary<string, string?>
    {
        ["Jwt:Secret"] = "endpoint-test-jwt-secret-not-for-production-32chars",
        ["SeedUsers:SellerUsername"] = "demo",
        ["SeedUsers:SellerPassword"] = TestPassword,
        ["SeedUsers:SellerEmail"] = "demo@example.test",
        ["SeedUsers:SupportUsername"] = "support",
        ["SeedUsers:SupportPassword"] = TestPassword,
        ["SeedUsers:SupportEmail"] = "support@example.test"
    };

    private static async Task SeedTestUsersAsync(WebApplicationFactory<Program> factory)
    {
        using var scope = factory.Services.CreateScope();
        var environment = scope.ServiceProvider.GetRequiredService<IHostEnvironment>();
        await SeedData.SeedUsersAsync(factory.Services, environment);
    }

    private static async Task<T> ReadSuccessfulJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");

        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response body for {typeof(T).Name}. Status: {response.StatusCode}, Body: {body}");

        return payload!;
    }

    private sealed record LoginPayload(string Access, string Refresh, UserPayload User);
    private sealed record RefreshPayload(string Access);
    private sealed record UserPayload(int Id, string Username, string? Email, string Role, [property: JsonPropertyName("is_staff")] bool IsStaff, [property: JsonPropertyName("is_superuser")] bool IsSuperuser);
}
