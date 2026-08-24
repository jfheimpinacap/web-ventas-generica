using JemNexus.Api.Services;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CustomerTextNormalizerTests
{
    [Fact]
    public void MultilinePreservesInternalLinesAndNormalizesLineEndings()
    {
        var input = "\r\n- Motor diésel  \r\n- Balde de 1,2 m³\r\n\r\nIncluye manuales\r\n";
        Assert.Equal("- Motor diésel\n- Balde de 1,2 m³\n\nIncluye manuales", CustomerTextNormalizer.Multiline(input));
    }

    [Fact]
    public void MultilineRemovesControlsAndEmptyInputWhileSingleLineBehaviorIsUnchanged()
    {
        Assert.Equal("uno\ndos", CustomerTextNormalizer.Multiline("uno\u0000\ndos"));
        Assert.Null(CustomerTextNormalizer.Multiline(" \r\n\t "));
        Assert.Equal("uno dos", CustomerTextNormalizer.Optional(" uno\r\n dos "));
    }
}
