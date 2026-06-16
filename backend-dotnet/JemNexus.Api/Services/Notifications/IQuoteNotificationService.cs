using JemNexus.Api.Models;

namespace JemNexus.Api.Services.Notifications;

public interface IQuoteNotificationService
{
    Task<QuoteNotificationResult> SendNewQuoteRequestAsync(QuoteRequest quoteRequest, CancellationToken cancellationToken = default);
    Task<QuoteNotificationResult> SendTestNotificationAsync(CancellationToken cancellationToken = default);
}
