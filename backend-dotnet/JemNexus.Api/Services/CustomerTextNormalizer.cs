using System.Globalization;
using System.Text;

namespace JemNexus.Api.Services;

public static class CustomerTextNormalizer
{
    public static string Visible(string? value) => string.Join(' ', (value ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    public static string? Optional(string? value) { var normalized = Visible(value); return normalized.Length == 0 ? null : normalized; }
    public static string Search(string? value)
    {
        var decomposed = Visible(value).Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (var character in decomposed)
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark) builder.Append(char.ToUpperInvariant(character));
        return builder.ToString().Normalize(NormalizationForm.FormC);
    }
}
