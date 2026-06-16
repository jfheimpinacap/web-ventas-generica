namespace JemNexus.Api.Options;

public static class EmailSecurityModes
{
    public const string Auto = nameof(Auto);
    public const string StartTls = nameof(StartTls);
    public const string StartTlsWhenAvailable = nameof(StartTlsWhenAvailable);
    public const string SslOnConnect = nameof(SslOnConnect);
    public const string None = nameof(None);

    private static readonly ISet<string> SupportedModes = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        Auto,
        StartTls,
        StartTlsWhenAvailable,
        SslOnConnect,
        None
    };

    public static bool IsSupported(string? value) => !string.IsNullOrWhiteSpace(value) && SupportedModes.Contains(value.Trim());

    public static string Normalize(string value) => SupportedModes.First(mode => string.Equals(mode, value.Trim(), StringComparison.OrdinalIgnoreCase));
}
