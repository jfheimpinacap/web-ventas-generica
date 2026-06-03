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
    [Fact]
    public async Task LoginWithValidCredentialsReturnsAccessRefreshAndUser()
    {
        await using var factory = CreateFactory();
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = "correct-password" });
        var payload = await response.Content.ReadFromJsonAsync<LoginPayload>();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.Access));
        Assert.False(string.IsNullOrWhiteSpace(payload.Refresh));
        Assert.Equal("demo", payload.User.Username);
        Assert.Equal(AppRoles.Seller, payload.User.Role);
        Assert.True(payload.User.IsStaff);
    }

    [Fact]
    public async Task LoginWithInvalidCredentialsReturnsUnauthorized()
    {
        await using var factory = CreateFactory();
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = "wrong-password" });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task MeWithoutBearerTokenReturnsUnauthorized()
    {
        await using var factory = CreateFactory();
        var client = factory.CreateClient();

        var response = await client.GetAsync("/api/auth/me/");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task MeWithBearerTokenReturnsCurrentUser()
    {
        await using var factory = CreateFactory();
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = "correct-password" });
        var login = await loginResponse.Content.ReadFromJsonAsync<LoginPayload>();
        Assert.NotNull(login);

        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        var response = await client.GetAsync("/api/auth/me/");
        var user = await response.Content.ReadFromJsonAsync<UserPayload>();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.NotNull(user);
        Assert.Equal("demo", user.Username);
        Assert.Equal(AppRoles.Seller, user.Role);
    }

    [Fact]
    public async Task RefreshWithPersistedRefreshTokenReturnsNewAccessToken()
    {
        await using var factory = CreateFactory();
        await SeedUserAsync(factory, "demo", "correct-password");
        var client = factory.CreateClient();
        var loginResponse = await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = "correct-password" });
        var login = await loginResponse.Content.ReadFromJsonAsync<LoginPayload>();
        Assert.NotNull(login);

        var response = await client.PostAsJsonAsync("/api/auth/refresh/", new { refresh = login.Refresh });
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
