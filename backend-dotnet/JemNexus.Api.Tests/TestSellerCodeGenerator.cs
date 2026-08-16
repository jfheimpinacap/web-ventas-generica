using System.Globalization;
using JemNexus.Api.Services;

namespace JemNexus.Api.Tests;

internal sealed class TestSellerCodeGenerator : ISellerCodeGenerator
{
    private long _next;

    public Task<string> GenerateAsync(CancellationToken cancellationToken = default)
    {
        var value = Interlocked.Increment(ref _next);
        return Task.FromResult($"VEN-{value.ToString("D4", CultureInfo.InvariantCulture)}");
    }
}
