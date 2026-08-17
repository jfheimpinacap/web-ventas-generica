using JemNexus.Api.Services;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class ChileanRutTests
{
    [Theory]
    [InlineData("12.345.678-5", "12345678-5")]
    [InlineData("12345678-5", "12345678-5")]
    [InlineData("123456785", "12345678-5")]
    [InlineData(" 6-k ", "6-K")]
    [InlineData("6K", "6-K")]
    public void ValidSyntheticRutIsCanonical(string input, string expected)
    {
        Assert.True(ChileanRut.TryNormalize(input, out var actual));
        Assert.Equal(expected, actual);
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("-")]
    [InlineData("12345678-4")]
    [InlineData("12A45678-5")]
    [InlineData("123-45-6")]
    public void InvalidRutIsRejected(string input) => Assert.False(ChileanRut.TryNormalize(input, out _));
}
