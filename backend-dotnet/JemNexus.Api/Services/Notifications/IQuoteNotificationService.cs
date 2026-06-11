using JemNexus.Api.Models;

namespace JemNexus.Api.Services.Notifications;

public interface IQuoteNotificationService
{
    Task SendNewQuoteRequestAsync(QuoteRequest quoteRequest, CancellationToken cancellationToken = default);
}
