using System.Text.Json.Serialization;

namespace JemNexus.Api.Services.Notifications;

public sealed record QuoteNotificationDiagnosticResponse(
    bool Success,
    bool Skipped,
    [property: JsonPropertyName("recipients_count")] int RecipientsCount,
    [property: JsonPropertyName("smtp_host")] string SmtpHost,
    [property: JsonPropertyName("smtp_port")] int SmtpPort,
    [property: JsonPropertyName("security_mode")] string SecurityMode,
    string Message,
    [property: JsonPropertyName("error_code")] string? ErrorCode)
{
    public static QuoteNotificationDiagnosticResponse FromResult(QuoteNotificationResult result) => new(
        result.Success,
        result.Skipped,
        result.RecipientsCount,
        result.SmtpHost,
        result.SmtpPort,
        result.SecurityMode,
        string.IsNullOrWhiteSpace(result.ErrorMessage) ? (result.Success ? "SMTP notification sent." : "SMTP notification failed.") : result.ErrorMessage,
        string.IsNullOrWhiteSpace(result.ErrorCode) ? null : result.ErrorCode);
}
