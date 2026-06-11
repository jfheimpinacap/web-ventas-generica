using System.Net;
using System.Net.Http.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using JemNexus.Api.Services.Notifications;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialPublicQuoteEndpointTests : IDisposable
{
    private const string TestPassword = "DummyPassword123!";
    private readonly CapturingQuoteNotificationService _notificationService = new();
    private readonly CommercialPublicQuoteApiFactory _factory;

    public CommercialPublicQuoteEndpointTests()
    {
        _factory = new CommercialPublicQuoteApiFactory(_notificationService);
    }

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task PublicQuoteRequestCreatesRecordAndAttemptsSellerNotificationWithoutToken()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/public/quote-requests/", new
        {
            product = 1,
            customer_name = "Cliente Público",
            customer_phone = "+56912345678",
            customer_email = "cliente@example.test",
            company_name = "Empresa Pública",
            city = "Santiago",
            preferred_contact_method = PreferredContactMethods.Email,
            message = "Necesito cotizar este equipo"
        });

        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.DoesNotContain("password", body, StringComparison.OrdinalIgnoreCase);
        Assert.Equal(1, _notificationService.AttemptCount);
        Assert.NotNull(_notificationService.LastQuote);
        Assert.Equal("cliente@example.test", _notificationService.LastQuote!.CustomerEmail);

        using var scope = _factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var saved = await dbContext.QuoteRequests.SingleAsync(quote => quote.CustomerName == "Cliente Público");
        Assert.Equal(QuoteStatuses.New, saved.Status);
        Assert.Equal(1, saved.ProductId);
    }

    [Fact]
    public async Task PublicQuoteRequestIsStillSavedWhenSellerNotificationFails()
    {
        await _factory.SeedCommercialDataAsync();
        _notificationService.ExceptionToThrow = new InvalidOperationException("smtp-secret-password");
        using var client = _factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/public/quote-requests/", new
        {
            customer_name = "Cliente Sin Email",
            customer_phone = "+56900000000",
            message = "Cotización general"
        });

        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.DoesNotContain("smtp-secret-password", body, StringComparison.OrdinalIgnoreCase);
        Assert.Equal(1, _notificationService.AttemptCount);

        using var scope = _factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.True(await dbContext.QuoteRequests.AnyAsync(quote => quote.CustomerName == "Cliente Sin Email"));
    }

    [Fact]
    public async Task AdminQuoteStatusEndpointStillRequiresToken()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.PatchAsJsonAsync("/api/quote-requests/1/", new { status = QuoteStatuses.Contacted });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    public sealed class CommercialPublicQuoteApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("CommercialPublicQuoteEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();
        private readonly CapturingQuoteNotificationService _notificationService;

        public CommercialPublicQuoteApiFactory(CapturingQuoteNotificationService notificationService)
        {
            _notificationService = notificationService;
        }

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configurationBuilder) => configurationBuilder.AddInMemoryCollection(TestConfiguration));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<IQuoteNotificationService>();
                services.AddDbContext<JemNexusDbContext>(options => InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot));
                services.AddSingleton<IQuoteNotificationService>(_notificationService);
            });
        }

        public async Task SeedCommercialDataAsync()
        {
            using var scope = Services.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            if (await dbContext.Products.AnyAsync()) return;

            var category = new Category { Id = 1, Name = "Maquinaria", Slug = "maquinaria", IsActive = true };
            var product = new Product
            {
                Id = 1,
                Name = "Excavadora",
                Slug = "excavadora",
                Category = category,
                ProductType = ProductTypes.Machinery,
                Condition = ProductConditions.Used,
                StockStatus = StockStatuses.Available,
                IsPublished = true
            };

            dbContext.Categories.Add(category);
            dbContext.Products.Add(product);
            dbContext.QuoteRequests.Add(new QuoteRequest { Id = 1, Product = product, CustomerName = "Cliente", CustomerPhone = "+569", Message = "Cotizar", Status = QuoteStatuses.New });
            await dbContext.SaveChangesAsync();
        }
    }

    public sealed class CapturingQuoteNotificationService : IQuoteNotificationService
    {
        public int AttemptCount { get; private set; }
        public QuoteRequest? LastQuote { get; private set; }
        public Exception? ExceptionToThrow { get; set; }

        public Task SendNewQuoteRequestAsync(QuoteRequest quoteRequest, CancellationToken cancellationToken = default)
        {
            AttemptCount++;
            LastQuote = quoteRequest;
            if (ExceptionToThrow is not null) throw ExceptionToThrow;
            return Task.CompletedTask;
        }
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
}
