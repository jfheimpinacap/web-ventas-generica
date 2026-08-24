using System.Net;
using System.Net.Http.Headers;
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

public sealed class ApiSecurityHeadersEndpointTests
{
    private const string TestJwtSecret = "DummyJwtSecretForSecurityHeaderTests1234567890!";

    private static readonly IReadOnlyDictionary<string, string> ExpectedHeaders =
        new Dictionary<string, string>
        {
            ["Content-Security-Policy"] = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            ["X-Content-Type-Options"] = "nosniff",
            ["X-Frame-Options"] = "DENY",
            ["Referrer-Policy"] = "no-referrer",
            ["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()",
            ["X-XSS-Protection"] = "0",
            ["X-Permitted-Cross-Domain-Policies"] = "none"
        };

    [Theory]
    [InlineData("/api/health", HttpStatusCode.OK)]
    [InlineData("/api/not-found", HttpStatusCode.NotFound)]
    [InlineData("/api/auth/me", HttpStatusCode.Unauthorized)]
    public async Task TestResponsesContainTheCompleteBaselineOnce(string path, HttpStatusCode expectedStatus)
    {
        await using var factory = new SecurityHeadersApiFactory("Test");
        using var client = CreateHttpsClient(factory);
        using var response = await client.GetAsync(path);

        Assert.Equal(expectedStatus, response.StatusCode);
        AssertBaseline(response);
        Assert.False(response.Headers.Contains("Strict-Transport-Security"));
    }

    [Fact]
    public async Task ExistingPublicImageHeadersAndRangeBehaviorArePreserved()
    {
        await using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        const int productId = 163;
        const string publicPath = "/media/product-images/163/security-header.webp";
        byte[] imageBytes = [1, 2, 3, 4, 5, 6];

        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            db.Products.Add(new Product
            {
                Id = productId,
                Name = "Security header product",
                Slug = "security-header-product",
                Category = new Category
                {
                    Id = productId,
                    Name = "Security header category",
                    Slug = "security-header-category",
                    ProductType = ProductTypes.Machinery,
                    IsActive = true
                },
                ProductType = ProductTypes.Machinery,
                Condition = ProductConditions.New,
                StockStatus = StockStatuses.Available,
                IsPublished = true,
                Images = [new ProductImage { Image = publicPath, AltText = "Test", IsMain = true }]
            });
            await db.SaveChangesAsync();
        }

        var physicalPath = factory.PhysicalUploadPath(publicPath);
        Directory.CreateDirectory(Path.GetDirectoryName(physicalPath)!);
        await File.WriteAllBytesAsync(physicalPath, imageBytes);
        using var client = factory.CreateClient();

        using var response = await client.GetAsync(publicPath);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        AssertSingleHeader(response, "X-Content-Type-Options", "nosniff");
        AssertPublicRevalidationCache(response);
        Assert.Equal("image/webp", response.Content.Headers.ContentType?.MediaType);
        Assert.Null(response.Content.Headers.ContentDisposition);

        using var rangeRequest = new HttpRequestMessage(HttpMethod.Get, publicPath);
        rangeRequest.Headers.Range = new RangeHeaderValue(1, 3);
        using var rangeResponse = await client.SendAsync(rangeRequest);
        Assert.Equal(HttpStatusCode.PartialContent, rangeResponse.StatusCode);
        Assert.Equal(imageBytes[1..4], await rangeResponse.Content.ReadAsByteArrayAsync());
        AssertSingleHeader(rangeResponse, "X-Content-Type-Options", "nosniff");
        AssertPublicRevalidationCache(rangeResponse);
    }

    [Fact]
    public async Task QaSwaggerOmitsOnlyContentSecurityPolicyAndHsts()
    {
        await using var factory = new SecurityHeadersApiFactory("QA");
        using var client = CreateHttpsClient(factory);
        using var response = await client.GetAsync("/swagger/index.html");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.False(response.Headers.Contains("Content-Security-Policy"));
        Assert.False(response.Headers.Contains("Strict-Transport-Security"));
        foreach (var header in ExpectedHeaders.Where(header => header.Key != "Content-Security-Policy"))
        {
            AssertSingleHeader(response, header.Key, header.Value);
        }
    }

    [Fact]
    public async Task ProductionHttpsResponseContainsExactHstsAndSecurityBaseline()
    {
        await using var factory = new SecurityHeadersApiFactory("Production");
        using var client = CreateHttpsClient(factory, new Uri("https://api.jem-nexus.test"));
        using var response = await client.GetAsync("/api/health");

        var requestUri = Assert.IsType<Uri>(response.RequestMessage?.RequestUri);
        Assert.Equal(Uri.UriSchemeHttps, requestUri.Scheme);
        Assert.Equal("api.jem-nexus.test", requestUri.Host);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        AssertBaseline(response);
        AssertSingleHeader(response, "Strict-Transport-Security", "max-age=31536000");
        var hsts = response.Headers.GetValues("Strict-Transport-Security").Single();
        Assert.DoesNotContain("includeSubDomains", hsts, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("preload", hsts, StringComparison.OrdinalIgnoreCase);
    }

    private static HttpClient CreateHttpsClient(WebApplicationFactory<Program> factory, Uri? baseAddress = null) =>
        factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = baseAddress ?? new Uri("https://localhost"),
            AllowAutoRedirect = false
        });

    private static void AssertBaseline(HttpResponseMessage response)
    {
        foreach (var header in ExpectedHeaders)
        {
            AssertSingleHeader(response, header.Key, header.Value);
        }
    }

    private static void AssertSingleHeader(HttpResponseMessage response, string name, string expectedValue)
    {
        Assert.True(response.Headers.TryGetValues(name, out var values));
        Assert.Equal(expectedValue, Assert.Single(values));
    }

    private static void AssertPublicRevalidationCache(HttpResponseMessage response)
    {
        Assert.NotNull(response.Headers.CacheControl);
        Assert.True(response.Headers.CacheControl.Public);
        Assert.Equal(TimeSpan.Zero, response.Headers.CacheControl.MaxAge);
        Assert.True(response.Headers.CacheControl.MustRevalidate);
        Assert.False(response.Headers.CacheControl.Private);
        Assert.False(response.Headers.CacheControl.NoStore);
    }

    private sealed class SecurityHeadersApiFactory(string environment) : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName($"ApiSecurityHeaders-{environment}");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment(environment);
            builder.UseSetting("JWT_SECRET", TestJwtSecret);
            builder.ConfigureAppConfiguration((_, configuration) => configuration.AddInMemoryCollection(TestConfiguration));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<ISellerCodeGenerator>();
                services.AddSingleton<ISellerCodeGenerator, TestSellerCodeGenerator>();
                services.AddDbContext<JemNexusDbContext>(options =>
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
            });
        }
    }

    private static readonly IReadOnlyDictionary<string, string?> TestConfiguration = new Dictionary<string, string?>
    {
        ["Jwt:Issuer"] = "JEM Nexus API Test",
        ["Jwt:Audience"] = "JEM Nexus Frontend Test",
        ["Jwt:AccessTokenMinutes"] = "60",
        ["Jwt:RefreshTokenDays"] = "7",
        ["SeedUsers:SellerUsername"] = "security-seller",
        ["SeedUsers:SellerPassword"] = "DummyPassword123!",
        ["SeedUsers:SellerEmail"] = "security-seller@example.test",
        ["SeedUsers:SupportUsername"] = "security-support",
        ["SeedUsers:SupportPassword"] = "DummyPassword123!",
        ["SeedUsers:SupportEmail"] = "security-support@example.test"
    };
}
