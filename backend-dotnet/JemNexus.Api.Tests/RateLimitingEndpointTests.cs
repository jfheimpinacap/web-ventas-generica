using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class RateLimitingEndpointTests
{
    private const string TestPassword = "DummyPassword123!";

    [Fact]
    public async Task LoginReturnsSafeProblemDetailsAfterSpecificLimit()
    {
        await using var factory = new RateLimitFactory(new Dictionary<string, string?>
        {
            ["RateLimiting:Enabled"] = "true",
            ["RateLimiting:EnableInTest"] = "true",
            ["RateLimiting:AuthLogin:PermitLimit"] = "2"
        });
        using var client = factory.CreateClient();
        var credentials = new { username = "rate-limit-user", password = "secret-not-returned" };

        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/auth/login", credentials)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/auth/login", credentials)).StatusCode);
        var rejected = await client.PostAsJsonAsync("/api/auth/login", credentials);
        var body = await rejected.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.TooManyRequests, rejected.StatusCode);
        Assert.Equal("application/problem+json", rejected.Content.Headers.ContentType?.MediaType);
        Assert.Contains("Demasiadas solicitudes.", body);
        Assert.Contains("429", body);
        Assert.DoesNotContain("rate-limit-user", body);
        Assert.DoesNotContain("secret-not-returned", body);
        Assert.DoesNotContain(RateLimitPolicies.AuthLogin, body);
        Assert.True(long.TryParse(rejected.Headers.RetryAfter?.Delta?.TotalSeconds.ToString("0")
            ?? rejected.Headers.GetValues("Retry-After").Single(), out var seconds) && seconds > 0);
    }

    [Fact]
    public async Task AnonymousGlobalLimitCoversPublicReads()
    {
        await using var factory = new RateLimitFactory(new Dictionary<string, string?>
        {
            ["RateLimiting:Enabled"] = "true",
            ["RateLimiting:EnableInTest"] = "true",
            ["RateLimiting:GlobalAnonymous:PermitLimit"] = "1"
        });
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/health")).StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, (await client.GetAsync("/api/health")).StatusCode);
    }

    [Fact]
    public async Task PublicSubmissionRejectsSecondRequestWithItsSpecificLimit()
    {
        var settings = EnabledRateLimitingSettings();
        settings["RateLimiting:PublicSubmission:PermitLimit"] = "1";
        await using var factory = new RateLimitFactory(settings);
        using var client = factory.CreateClient();
        var invalidRequest = new
        {
            customer_name = "",
            customer_email = "not-an-email",
            message = ""
        };

        var first = await client.PostAsJsonAsync("/api/public/quote-requests", invalidRequest);
        var second = await client.PostAsJsonAsync("/api/public/quote-requests", invalidRequest);

        Assert.Equal(HttpStatusCode.BadRequest, first.StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, second.StatusCode);
    }

    [Fact]
    public async Task AuthenticatedGlobalLimitKeepsSeparateBucketsPerUser()
    {
        var settings = EnabledRateLimitingSettings();
        settings["RateLimiting:GlobalAuthenticated:PermitLimit"] = "1";
        await using var factory = new RateLimitFactory(settings);
        using var loginClient = factory.CreateClient();
        var sellerToken = await LoginAccessTokenAsync(loginClient, "demo");
        var supportToken = await LoginAccessTokenAsync(loginClient, "support");
        using var sellerClient = AuthenticatedClient(factory, sellerToken);
        using var supportClient = AuthenticatedClient(factory, supportToken);

        var sellerFirst = await sellerClient.GetAsync("/api/auth/me");
        var sellerSecond = await sellerClient.GetAsync("/api/auth/me");
        var supportFirst = await supportClient.GetAsync("/api/auth/me");

        Assert.NotEqual(HttpStatusCode.TooManyRequests, sellerFirst.StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, sellerSecond.StatusCode);
        Assert.NotEqual(HttpStatusCode.TooManyRequests, supportFirst.StatusCode);
    }

    [Fact]
    public async Task AuthenticatedWriteRejectsSecondMutationWithItsSpecificLimit()
    {
        var settings = EnabledRateLimitingSettings();
        settings["RateLimiting:AuthenticatedWrite:PermitLimit"] = "1";
        await using var factory = new RateLimitFactory(settings);
        using var loginClient = factory.CreateClient();
        var sellerToken = await LoginAccessTokenAsync(loginClient, "demo");
        using var client = AuthenticatedClient(factory, sellerToken);
        var invalidCustomer = new
        {
            business_name = "",
            rut = "",
            email = "not-an-email"
        };

        var first = await client.PostAsJsonAsync("/api/admin/customers", invalidCustomer);
        var second = await client.PostAsJsonAsync("/api/admin/customers", invalidCustomer);

        Assert.Equal(HttpStatusCode.BadRequest, first.StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, second.StatusCode);
    }

    [Fact]
    public async Task TestEnvironmentBypassesSmallLimitsByDefault()
    {
        await using var factory = new RateLimitFactory(new Dictionary<string, string?>
        {
            ["RateLimiting:Enabled"] = "true",
            ["RateLimiting:GlobalAnonymous:PermitLimit"] = "1"
        });
        using var client = factory.CreateClient();
        for (var attempt = 0; attempt < 3; attempt++)
            Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/health")).StatusCode);
    }

    [Fact]
    public void EndpointsExposeNamedRateLimitMetadata()
    {
        using var factory = new RateLimitFactory();
        _ = factory.CreateClient();
        var endpoints = factory.Services.GetRequiredService<EndpointDataSource>().Endpoints;
        AssertPolicy(endpoints, "/api/auth/login", "POST", RateLimitPolicies.AuthLogin);
        AssertPolicy(endpoints, "/api/auth/refresh", "POST", RateLimitPolicies.AuthSession);
        AssertPolicy(endpoints, "/api/auth/logout", "POST", RateLimitPolicies.AuthSession);
        AssertPolicy(endpoints, "/api/public/quote-requests", "POST", RateLimitPolicies.PublicSubmission);
        AssertPolicy(endpoints, "/api/public/products/{idOrSlug}/technical-sheet/file", "GET", RateLimitPolicies.Download);
        AssertPolicy(endpoints, "/api/quote-notifications/test", "POST", RateLimitPolicies.NotificationTest);
        AssertPolicy(endpoints, "/api/admin/commercial-quotes/issue", "POST", RateLimitPolicies.QuoteIssue);
        AssertPolicy(endpoints, "/api/product-images", "POST", RateLimitPolicies.Upload);
        AssertPolicy(endpoints, "/api/technical-sheets/", "POST", RateLimitPolicies.Upload);
        AssertPolicy(endpoints, "/api/technical-sheets/{id:int}/file", "POST", RateLimitPolicies.Upload);
        AssertPolicy(endpoints, "/api/technical-sheets/{id:int}/file", "GET", RateLimitPolicies.Download);
        AssertPolicy(endpoints, "/api/admin/customers", "POST", RateLimitPolicies.AuthenticatedWrite);
        AssertPolicy(endpoints, "/api/admin/customers/{id:int}", "PUT", RateLimitPolicies.AuthenticatedWrite);
        AssertPolicy(endpoints, "/api/admin/users", "POST", RateLimitPolicies.AuthenticatedWrite);
        AssertPolicy(endpoints, "/api/admin/users/{id:int}", "DELETE", RateLimitPolicies.AuthenticatedWrite);
    }

    [Fact]
    public void InvalidRuleFailsAtStartupWithClearMessage()
    {
        using var factory = new RateLimitFactory(new Dictionary<string, string?>
        {
            ["RateLimiting:AuthLogin:PermitLimit"] = "0"
        });
        var error = Assert.ThrowsAny<Exception>(() => factory.CreateClient());
        Assert.Contains("RateLimiting:AuthLogin", error.ToString());
    }

    private static void AssertPolicy(IReadOnlyList<Endpoint> endpoints, string path, string method, string policy)
    {
        var endpoint = endpoints.OfType<RouteEndpoint>().Single(candidate =>
            candidate.RoutePattern.RawText == path
            && candidate.Metadata.GetMetadata<HttpMethodMetadata>()?.HttpMethods.Contains(method) == true);
        Assert.Contains(endpoint.Metadata.GetOrderedMetadata<EnableRateLimitingAttribute>(), value => value.PolicyName == policy);
    }

    private static Dictionary<string, string?> EnabledRateLimitingSettings()
    {
        const string highPermitLimit = "100";
        const string longWindow = "3600";
        string[] rules =
        [
            "GlobalAnonymous", "GlobalAuthenticated", "AuthLogin", "AuthSession", "PublicSubmission",
            "AuthenticatedWrite", "Upload", "Download", "NotificationTest", "QuoteIssue"
        ];
        var settings = new Dictionary<string, string?>
        {
            ["RateLimiting:Enabled"] = "true",
            ["RateLimiting:EnableInTest"] = "true",
            ["SeedUsers:SellerUsername"] = "demo",
            ["SeedUsers:SellerPassword"] = TestPassword,
            ["SeedUsers:SellerEmail"] = "demo@example.test",
            ["SeedUsers:SupportUsername"] = "support",
            ["SeedUsers:SupportPassword"] = TestPassword,
            ["SeedUsers:SupportEmail"] = "support@example.test"
        };
        foreach (var rule in rules)
        {
            settings[$"RateLimiting:{rule}:PermitLimit"] = highPermitLimit;
            settings[$"RateLimiting:{rule}:WindowSeconds"] = longWindow;
        }

        return settings;
    }

    private static async Task<string> LoginAccessTokenAsync(HttpClient client, string username)
    {
        var response = await client.PostAsJsonAsync("/api/auth/login", new { username, password = TestPassword });
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<LoginPayload>();
        Assert.NotNull(payload);
        return payload.Access;
    }

    private static HttpClient AuthenticatedClient(WebApplicationFactory<Program> factory, string accessToken)
    {
        var client = factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        return client;
    }

    private sealed class RateLimitFactory(IReadOnlyDictionary<string, string?>? settings = null) : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("RateLimitingEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configuration) =>
                configuration.AddInMemoryCollection(settings ?? new Dictionary<string, string?>()));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<ISellerCodeGenerator>();
                services.AddSingleton<ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.AddDbContext<JemNexusDbContext>(options =>
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }
    }

    private sealed record LoginPayload(string Access);
}
