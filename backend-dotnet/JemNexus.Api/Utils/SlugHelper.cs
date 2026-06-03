using System.Globalization;
using System.Text;

namespace JemNexus.Api.Utils;

public static class SlugHelper
{
    public static string GenerateSlug(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return string.Empty;
        }

        var normalizedText = text.Trim().ToLowerInvariant().Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(normalizedText.Length);
        var previousWasSeparator = false;

        foreach (var character in normalizedText)
        {
            var unicodeCategory = CharUnicodeInfo.GetUnicodeCategory(character);
            if (unicodeCategory == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(character))
            {
                builder.Append(character);
                previousWasSeparator = false;
                continue;
            }

            if (char.IsWhiteSpace(character) || character == '-' || character == '_' || character == '/')
            {
                AppendSeparator(builder, ref previousWasSeparator);
            }
        }

        return builder.ToString().Trim('-').Normalize(NormalizationForm.FormC);
    }

    private static void AppendSeparator(StringBuilder builder, ref bool previousWasSeparator)
    {
        if (builder.Length == 0 || previousWasSeparator)
        {
            return;
        }

        builder.Append('-');
        previousWasSeparator = true;
    }
}
