using System.Net.Sockets;
using System.Text;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using MailKit;
using MailKit.Net.Smtp;
using MailKit.Security;
using Microsoft.Extensions.Options;
using MimeKit;
using MimeKit.Utils;

namespace JemNexus.Api.Services.Notifications;

public sealed class SmtpQuoteNotificationService : IQuoteNotificationService
{
    private const string NewQuoteSubject = "Nueva solicitud de cotización - JEM Nexus";
    private const string TestSubject = "Prueba de notificación SMTP - JEM Nexus";
    private const string TestBody = "Prueba de configuración SMTP del sistema de cotizaciones JEM Nexus.";
    private readonly EmailOptions _emailOptions;
    private readonly QuoteNotificationOptions _quoteNotificationOptions;
    private readonly FrontendOptions _frontendOptions;
    private readonly ILogger<SmtpQuoteNotificationService> _logger;

    public SmtpQuoteNotificationService(
        IOptions<EmailOptions> emailOptions,
        IOptions<QuoteNotificationOptions> quoteNotificationOptions,
        IOptions<FrontendOptions> frontendOptions,
        ILogger<SmtpQuoteNotificationService> logger)
    {
        _emailOptions = emailOptions.Value;
        _quoteNotificationOptions = quoteNotificationOptions.Value;
        _frontendOptions = frontendOptions.Value;
        _logger = logger;
    }

    public async Task<QuoteNotificationResult> SendNewQuoteRequestAsync(QuoteRequest quoteRequest, CancellationToken cancellationToken = default)
    {
        var body = BuildQuoteBody(quoteRequest);
        var result = await SendAsync(NewQuoteSubject, body, quoteRequest.CustomerEmail, cancellationToken);
        LogResult(result, "quote request");
        return result;
    }

    public async Task<QuoteNotificationResult> SendTestNotificationAsync(CancellationToken cancellationToken = default)
    {
        var result = await SendAsync(TestSubject, TestBody, replyToAddress: null, cancellationToken);
        LogResult(result, "SMTP test");
        return result;
    }

    private async Task<QuoteNotificationResult> SendAsync(string subject, string body, string? replyToAddress, CancellationToken cancellationToken)
    {
        var recipients = _quoteNotificationOptions.GetRecipientList();
        var securityMode = _emailOptions.ResolveSecurityMode();
        var baseResult = QuoteNotificationResult.CreateBase(recipients.Count, _emailOptions.SmtpHost, _emailOptions.SmtpPort, securityMode);
        var missing = GetMissingConfiguration(recipients);
        if (missing.Count > 0)
        {
            return baseResult with
            {
                Skipped = true,
                ErrorCode = "smtp_configuration_missing",
                ErrorMessage = "Required SMTP configuration is incomplete."
            };
        }

        var timeout = TimeSpan.FromSeconds(Math.Clamp(_emailOptions.TimeoutSeconds, 1, 300));
        using var timeoutCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeoutCts.CancelAfter(timeout);

        try
        {
            var message = BuildMessage(subject, body, recipients, replyToAddress);
            using var client = new SmtpClient { Timeout = (int)timeout.TotalMilliseconds };
            await client.ConnectAsync(_emailOptions.SmtpHost.Trim(), _emailOptions.SmtpPort, ToMailKitSecurity(securityMode), timeoutCts.Token);

            if (!string.IsNullOrWhiteSpace(_emailOptions.Username))
            {
                await client.AuthenticateAsync(_emailOptions.Username.Trim(), _emailOptions.Password, timeoutCts.Token);
            }

            await client.SendAsync(message, timeoutCts.Token);
            await client.DisconnectAsync(true, CancellationToken.None);

            return baseResult with { Success = true, ErrorMessage = "SMTP notification sent." };
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return baseResult with { ErrorCode = "smtp_timeout", ErrorMessage = $"SMTP operation timed out after {timeout.TotalSeconds:0} seconds." };
        }
        catch (AuthenticationException exception)
        {
            return baseResult with { ErrorCode = "smtp_authentication_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP authentication failed.") };
        }
        catch (SslHandshakeException exception)
        {
            return baseResult with { ErrorCode = "smtp_tls_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP TLS/SSL negotiation failed.") };
        }
        catch (ServiceNotConnectedException exception)
        {
            return baseResult with { ErrorCode = "smtp_connection_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP connection failed.") };
        }
        catch (SmtpCommandException exception) when (exception.ErrorCode == SmtpErrorCode.RecipientNotAccepted)
        {
            return baseResult with { ErrorCode = "smtp_recipient_rejected", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP recipient was rejected.") };
        }
        catch (SmtpCommandException exception)
        {
            return baseResult with { ErrorCode = "smtp_command_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP command failed.") };
        }
        catch (SmtpProtocolException exception)
        {
            return baseResult with { ErrorCode = "smtp_protocol_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP protocol error.") };
        }
        catch (SocketException exception)
        {
            return baseResult with { ErrorCode = "smtp_connection_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP connection failed.") };
        }
        catch (IOException exception)
        {
            return baseResult with { ErrorCode = "smtp_connection_failed", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP connection failed.") };
        }
        catch (Exception exception)
        {
            return baseResult with { ErrorCode = "smtp_error", ErrorMessage = SanitizeExceptionMessage(exception, "SMTP notification failed.") };
        }
    }

    private IReadOnlyList<string> GetMissingConfiguration(IReadOnlyCollection<string> recipients)
    {
        var missing = new List<string>();
        if (string.IsNullOrWhiteSpace(_emailOptions.SmtpHost)) missing.Add("Email:SmtpHost");
        if (string.IsNullOrWhiteSpace(_emailOptions.FromAddress)) missing.Add("Email:FromAddress");
        if (string.IsNullOrWhiteSpace(_emailOptions.Password)) missing.Add("Email:Password");
        if (recipients.Count == 0) missing.Add("QuoteNotifications:Recipients");
        return missing;
    }

    private MimeMessage BuildMessage(string subject, string body, IEnumerable<string> recipients, string? replyToAddress)
    {
        var message = new MimeMessage { Subject = subject };
        var fromName = string.IsNullOrWhiteSpace(_emailOptions.FromName) ? _emailOptions.FromAddress : _emailOptions.FromName;
        message.From.Add(new MailboxAddress(fromName, _emailOptions.FromAddress));
        foreach (var recipient in recipients) message.To.Add(MailboxAddress.Parse(recipient));
        if (!string.IsNullOrWhiteSpace(replyToAddress) && MailboxAddress.TryParse(replyToAddress, out var replyTo)) message.ReplyTo.Add(replyTo);
        message.MessageId = MimeUtils.GenerateMessageId(_emailOptions.SmtpHost);
        message.Body = new TextPart("plain") { Text = body };
        return message;
    }

    private static SecureSocketOptions ToMailKitSecurity(string securityMode) => securityMode switch
    {
        EmailSecurityModes.Auto => SecureSocketOptions.Auto,
        EmailSecurityModes.StartTls => SecureSocketOptions.StartTls,
        EmailSecurityModes.StartTlsWhenAvailable => SecureSocketOptions.StartTlsWhenAvailable,
        EmailSecurityModes.SslOnConnect => SecureSocketOptions.SslOnConnect,
        EmailSecurityModes.None => SecureSocketOptions.None,
        _ => SecureSocketOptions.Auto
    };

    private void LogResult(QuoteNotificationResult result, string context)
    {
        if (result.Success)
        {
            _logger.LogInformation("Quote notification {Context} email sent via {SmtpHost}:{SmtpPort} using {SecurityMode} to {RecipientsCount} configured recipients.", context, result.SmtpHost, result.SmtpPort, result.SecurityMode, result.RecipientsCount);
            return;
        }

        if (result.Skipped)
        {
            _logger.LogWarning("Quote notification {Context} skipped. Code: {ErrorCode}. Message: {ErrorMessage}. SMTP: {SmtpHost}:{SmtpPort}. Security: {SecurityMode}. Recipients: {RecipientsCount}.", context, result.ErrorCode, result.ErrorMessage, result.SmtpHost, result.SmtpPort, result.SecurityMode, result.RecipientsCount);
            return;
        }

        _logger.LogError("Quote notification {Context} failed. Code: {ErrorCode}. Message: {ErrorMessage}. SMTP: {SmtpHost}:{SmtpPort}. Security: {SecurityMode}. Recipients: {RecipientsCount}.", context, result.ErrorCode, result.ErrorMessage, result.SmtpHost, result.SmtpPort, result.SecurityMode, result.RecipientsCount);
    }

    private string BuildQuoteBody(QuoteRequest quoteRequest)
    {
        var adminUrl = BuildAdminQuoteUrl();
        var product = quoteRequest.Product?.Name ?? "Sin producto asociado";
        var productIdentifier = quoteRequest.Product is null ? "-" : $"ID {quoteRequest.Product.Id} / slug {quoteRequest.Product.Slug}";
        var builder = new StringBuilder();
        builder.AppendLine("Nueva solicitud de cotización recibida desde el sitio web JEM Nexus.");
        builder.AppendLine();
        builder.AppendLine("Datos del cliente:");
        builder.AppendLine($"Fecha/hora UTC: {quoteRequest.CreatedAt:yyyy-MM-dd HH:mm:ss}");
        builder.AppendLine($"Nombre: {ValueOrDash(quoteRequest.CustomerName)}");
        builder.AppendLine($"Empresa: {ValueOrDash(quoteRequest.CompanyName)}");
        builder.AppendLine($"Correo: {ValueOrDash(quoteRequest.CustomerEmail)}");
        builder.AppendLine($"Teléfono: {ValueOrDash(quoteRequest.CustomerPhone)}");
        builder.AppendLine();
        builder.AppendLine("Solicitud:");
        builder.AppendLine($"Producto: {product}");
        builder.AppendLine($"Identificador producto: {productIdentifier}");
        builder.AppendLine($"Mensaje: {ValueOrDash(quoteRequest.Message)}");
        builder.AppendLine("Origen: sitio web JEM Nexus");
        builder.AppendLine();
        builder.AppendLine("Gestión:");
        builder.AppendLine($"Revisar en panel vendedor: {adminUrl}");
        builder.AppendLine("Revisar panel vendedor y marcar gestión.");
        return builder.ToString();
    }

    private string BuildAdminQuoteUrl() => string.IsNullOrWhiteSpace(_frontendOptions.BaseUrl) ? "/admin/cotizaciones" : $"{_frontendOptions.BaseUrl.TrimEnd('/')}/admin/cotizaciones";
    private static string ValueOrDash(string? value) => string.IsNullOrWhiteSpace(value) ? "-" : value.Trim();
    private string SanitizeExceptionMessage(Exception exception, string fallback)
    {
        var message = string.IsNullOrWhiteSpace(exception.Message) ? fallback : exception.Message;
        foreach (var secret in new[] { _emailOptions.Password, _emailOptions.Username })
        {
            if (!string.IsNullOrWhiteSpace(secret)) message = message.Replace(secret, "[redacted]", StringComparison.OrdinalIgnoreCase);
        }
        return message.Length > 240 ? string.Concat(message.AsSpan(0, 240), "...") : message;
    }
}
