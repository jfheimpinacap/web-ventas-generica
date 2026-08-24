using System.Globalization;
using System.Text;

namespace JemNexus.Api.Services;

public static class CustomerTextNormalizer
{
    public static string Visible(string? value) => string.Join(' ', (value ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    public static string? Optional(string? value) { var normalized = Visible(value); return normalized.Length == 0 ? null : normalized; }
    public static string? Multiline(string? value)
    {
        if (value is null) return null;
        var normalized = value.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n');
        var builder = new StringBuilder(normalized.Length);
        foreach (var character in normalized)
            if (character == '\n' || !char.IsControl(character)) builder.Append(character);
        var lines = builder.ToString().Split('\n').Select(line => line.TrimEnd()).ToArray();
        var first = 0;
        while (first < lines.Length && string.IsNullOrWhiteSpace(lines[first])) first++;
        var last = lines.Length - 1;
        while (last >= first && string.IsNullOrWhiteSpace(lines[last])) last--;
        return first > last ? null : string.Join('\n', lines[first..(last + 1)]);
    }
    public static string Search(string? value)
    {
        var decomposed = Visible(value).Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (var character in decomposed)
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark) builder.Append(char.ToUpperInvariant(character));
        return builder.ToString().Normalize(NormalizationForm.FormC);
    }
}
