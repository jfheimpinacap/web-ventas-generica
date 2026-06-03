using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
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
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = "correct-password" });
        var payload = await response.Content.ReadFromJsonAsync<LoginPayload>();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
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
        await SeedUserAsync(factory, "demo", "correct-password");
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
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = "correct-password" });
        var login = await loginResponse.Content.ReadFromJsonAsync<LoginPayload>();
        Assert.NotNull(login);

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        var response = await client.GetAsync(mePath);
        var user = await response.Content.ReadFromJsonAsync<UserPayload>();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
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
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync(loginPath, new { username = "demo", password = "correct-password" });
        var login = await loginResponse.Content.ReadFromJsonAsync<LoginPayload>();
        Assert.NotNull(login);

        var response = await client.PostAsJsonAsync(refreshPath, new { refresh = login.Refresh });
        var payload = await response.Content.ReadFromJsonAsync<RefreshPayload>();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
    }

    private static WebApplicationFactory<Program> CreateFactory()
    {
        return new WebApplicationFactory<Program>()
            .WithWebHostBuilder(builder =>
            {
                builder.UseEnvironment("Test");
                builder.UseSetting("Jwt:Secret", "endpoint-test-jwt-secret-not-for-production-32chars");
                builder.ConfigureServices(services =>
                {
                    services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                    services.AddDbContext<JemNexusDbContext>(options =>
                        options.UseInMemoryDatabase(Guid.NewGuid().ToString()));
                });
            });
    }

    private static async Task SeedUserAsync(WebApplicationFactory<Program> factory, string username, string password)
    {
        using var scope = factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var user = new AppUser
        {
            Username = username,
            Email = $"{username}@example.test",
            Role = AppRoles.Seller,
            IsActive = true,
            IsStaff = true,
            IsSuperuser = false
        };
        user.PasswordHash = passwordHasher.HashPassword(user, password);
        dbContext.AppUsers.Add(user);
        await dbContext.SaveChangesAsync();
    }

    private sealed record LoginPayload(string Access, string Refresh, UserPayload User);
    private sealed record RefreshPayload(string Access);
    private sealed record UserPayload(int Id, string Username, string? Email, string Role, [property: JsonPropertyName("is_staff")] bool IsStaff, [property: JsonPropertyName("is_superuser")] bool IsSuperuser);
}
