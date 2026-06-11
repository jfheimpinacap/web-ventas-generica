namespace JemNexus.Api.Options;

public sealed class QuoteNotificationOptions
{
    public const string SectionName = "QuoteNotifications";
    public string Recipients { get; set; } = string.Empty;

    public IReadOnlyList<string> GetRecipientList() => Recipients
        .Split([',', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
        .Where(recipient => !string.IsNullOrWhiteSpace(recipient))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToList();
}
