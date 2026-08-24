using System.Net;
using System.Net.Http.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class HealthEndpointTests : IClassFixture<HealthEndpointTests.HealthApiFactory>
{
    private readonly HttpClient _client;

    public HealthEndpointTests(HealthApiFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Theory]
    [InlineData("/health")]
    [InlineData("/api/health")]
    [InlineData("/api/health/")]
    public async Task HealthEndpointsReturnOk(string path)
    {
        var response = await _client.GetAsync(path);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("/health")]
    [InlineData("/api/health")]
    [InlineData("/api/health/")]
    public async Task HealthEndpointsReturnExpectedPayload(string path)
    {
        var payload = await _client.GetFromJsonAsync<HealthResponse>(path);

        Assert.NotNull(payload);
        Assert.Equal("ok", payload.Status);
        Assert.Equal("JEM Nexus API", payload.App);
    }

    private sealed record HealthResponse(
        string Status,
        string App,
        string Environment,
        DateTimeOffset Timestamp);

    public sealed class HealthApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("HealthEndpointTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
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
}
