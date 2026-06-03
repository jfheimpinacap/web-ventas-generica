using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class HealthEndpointTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public HealthEndpointTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Theory]
    [InlineData("/health")]
    [InlineData("/api/health")]
    public async Task HealthEndpointsReturnOk(string path)
    {
        var response = await _client.GetAsync(path);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("/health")]
    [InlineData("/api/health")]
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
}
