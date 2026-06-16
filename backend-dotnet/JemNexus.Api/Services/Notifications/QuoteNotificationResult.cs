namespace JemNexus.Api.Services.Notifications;

public sealed record QuoteNotificationResult(
    bool Success,
    bool Skipped,
    string ErrorCode,
    string ErrorMessage,
    int RecipientsCount,
    string SmtpHost,
    int SmtpPort,
    string SecurityMode)
{
    public static QuoteNotificationResult CreateBase(int recipientsCount, string smtpHost, int smtpPort, string securityMode) =>
        new(false, false, string.Empty, string.Empty, recipientsCount, string.IsNullOrWhiteSpace(smtpHost) ? string.Empty : smtpHost.Trim(), smtpPort, securityMode);
}
