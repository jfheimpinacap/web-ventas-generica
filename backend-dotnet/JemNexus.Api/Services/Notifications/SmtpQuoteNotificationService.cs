using System.Net;
using System.Net.Mail;
using System.Text;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using Microsoft.Extensions.Options;

namespace JemNexus.Api.Services.Notifications;

public sealed class SmtpQuoteNotificationService : IQuoteNotificationService
{
    private const string Subject = "Nueva solicitud de cotización - JEM Nexus";
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

    public async Task SendNewQuoteRequestAsync(QuoteRequest quoteRequest, CancellationToken cancellationToken = default)
    {
        var recipients = _quoteNotificationOptions.GetRecipientList();
        if (!HasRequiredConfiguration(recipients))
        {
            _logger.LogWarning("Quote email notification skipped because SMTP host, from address, password, or recipients are not configured.");
            return;
        }

        using var message = BuildMessage(quoteRequest, recipients);
        using var client = new SmtpClient(_emailOptions.SmtpHost, _emailOptions.SmtpPort)
        {
            EnableSsl = _emailOptions.UseSsl,
            DeliveryMethod = SmtpDeliveryMethod.Network
        };

        if (!string.IsNullOrWhiteSpace(_emailOptions.Username))
        {
            client.Credentials = new NetworkCredential(_emailOptions.Username, _emailOptions.Password);
        }

        try
        {
            await client.SendMailAsync(message, cancellationToken);
        }
        catch (Exception exception)
        {
            _logger.LogError(exception, "Failed to send quote email notification to configured seller recipients.");
            throw;
        }
    }

    private bool HasRequiredConfiguration(IReadOnlyCollection<string> recipients) =>
        !string.IsNullOrWhiteSpace(_emailOptions.SmtpHost)
        && !string.IsNullOrWhiteSpace(_emailOptions.FromAddress)
        && !string.IsNullOrWhiteSpace(_emailOptions.Password)
        && recipients.Count > 0;

    private MailMessage BuildMessage(QuoteRequest quoteRequest, IEnumerable<string> recipients)
    {
        var from = string.IsNullOrWhiteSpace(_emailOptions.FromName)
            ? new MailAddress(_emailOptions.FromAddress)
            : new MailAddress(_emailOptions.FromAddress, _emailOptions.FromName);
        var message = new MailMessage
        {
            From = from,
            Subject = Subject,
            Body = BuildBody(quoteRequest),
            IsBodyHtml = false,
            BodyEncoding = Encoding.UTF8,
            SubjectEncoding = Encoding.UTF8
        };

        foreach (var recipient in recipients)
        {
            message.To.Add(recipient);
        }

        if (MailAddress.TryCreate(quoteRequest.CustomerEmail, out var replyTo))
        {
            message.ReplyToList.Add(replyTo);
        }

        return message;
    }

    private string BuildBody(QuoteRequest quoteRequest)
    {
        var adminUrl = BuildAdminQuoteUrl();
        var product = quoteRequest.Product?.Name ?? "Sin producto asociado";
        var productIdentifier = quoteRequest.Product is null
            ? "-"
            : $"ID {quoteRequest.Product.Id} / slug {quoteRequest.Product.Slug}";

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

    private string BuildAdminQuoteUrl()
    {
        if (string.IsNullOrWhiteSpace(_frontendOptions.BaseUrl)) return "/admin/cotizaciones";
        return $"{_frontendOptions.BaseUrl.TrimEnd('/')}/admin/cotizaciones";
    }

    private static string ValueOrDash(string? value) => string.IsNullOrWhiteSpace(value) ? "-" : value.Trim();
}
