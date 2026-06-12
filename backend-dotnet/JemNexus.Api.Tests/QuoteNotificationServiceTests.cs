using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services.Notifications;
using Microsoft.Extensions.Logging.Abstractions;
using OptionsFactory = Microsoft.Extensions.Options.Options;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class QuoteNotificationServiceTests
{
    [Fact]
    public void QuoteNotificationRecipientsSupportCommaAndSemicolonSeparators()
    {
        var options = new QuoteNotificationOptions
        {
            Recipients = "jmateluna@jem-nexus.cl,fheim@jem-nexus.cl; jmateluna@jem-nexus.cl"
        };

        var recipients = options.GetRecipientList();

        Assert.Equal(["jmateluna@jem-nexus.cl", "fheim@jem-nexus.cl"], recipients);
    }

    [Fact]
    public async Task QuoteNotificationServiceSkipsWithoutRequiredSmtpConfiguration()
    {
        var service = new SmtpQuoteNotificationService(
            OptionsFactory.Create(new EmailOptions()),
            OptionsFactory.Create(new QuoteNotificationOptions { Recipients = "jmateluna@jem-nexus.cl;fheim@jem-nexus.cl" }),
            OptionsFactory.Create(new FrontendOptions { BaseUrl = "https://jem-nexus.cl" }),
            NullLogger<SmtpQuoteNotificationService>.Instance);

        await service.SendNewQuoteRequestAsync(new QuoteRequest
        {
            CustomerName = "Cliente",
            CustomerEmail = "cliente@example.test",
            CustomerPhone = "+569",
            Message = "Cotizar",
            CreatedAt = DateTimeOffset.UtcNow
        });
    }
}
