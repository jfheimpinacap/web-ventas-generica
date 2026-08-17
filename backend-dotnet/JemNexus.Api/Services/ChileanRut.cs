namespace JemNexus.Api.Services;

public static class ChileanRut
{
    public const string InvalidMessage = "El RUT no es válido.";

    public static bool TryNormalize(string? input, out string canonical)
    {
        canonical = string.Empty;
        if (string.IsNullOrWhiteSpace(input)) return false;
        var compact = new string(input.Trim().Where(c => c is not '.' and not ' ').ToArray()).ToUpperInvariant();
        var hyphens = compact.Count(c => c == '-');
        if (hyphens > 1) return false;
        compact = compact.Replace("-", string.Empty, StringComparison.Ordinal);
        if (compact.Length < 2) return false;
        var body = compact[..^1];
        var supplied = compact[^1];
        if (!body.All(char.IsAsciiDigit) || !(char.IsAsciiDigit(supplied) || supplied == 'K')) return false;
        if (body.All(c => c == '0')) return false;

        var sum = 0;
        var multiplier = 2;
        for (var index = body.Length - 1; index >= 0; index--)
        {
            sum += (body[index] - '0') * multiplier;
            multiplier = multiplier == 7 ? 2 : multiplier + 1;
        }
        var remainder = 11 - sum % 11;
        var expected = remainder == 11 ? '0' : remainder == 10 ? 'K' : (char)('0' + remainder);
        if (supplied != expected) return false;
        canonical = $"{body}-{supplied}";
        return true;
    }
}
