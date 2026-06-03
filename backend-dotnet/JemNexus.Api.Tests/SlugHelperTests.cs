using JemNexus.Api.Utils;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class SlugHelperTests
{
    [Theory]
    [InlineData("Grúas Horquilla 3 Toneladas", "gruas-horquilla-3-toneladas")]
    [InlineData("Camión Pluma / Servicio Especial", "camion-pluma-servicio-especial")]
    [InlineData("  Repuestos   Hidráulicos  ", "repuestos-hidraulicos")]
    [InlineData("Producto --- Especial!!!", "producto-especial")]
    [InlineData("", "")]
    [InlineData(null, "")]
    public void GenerateSlugNormalizesInputSafely(string? input, string expected)
    {
        var slug = SlugHelper.GenerateSlug(input);

        Assert.Equal(expected, slug);
    }
}
