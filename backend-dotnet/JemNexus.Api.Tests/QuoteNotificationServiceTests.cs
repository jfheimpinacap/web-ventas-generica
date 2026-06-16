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

    [Theory]
    [InlineData("Auto", EmailSecurityModes.Auto)]
    [InlineData("StartTls", EmailSecurityModes.StartTls)]
    [InlineData("StartTlsWhenAvailable", EmailSecurityModes.StartTlsWhenAvailable)]
    [InlineData("SslOnConnect", EmailSecurityModes.SslOnConnect)]
    [InlineData("None", EmailSecurityModes.None)]
    [InlineData("starttls", EmailSecurityModes.StartTls)]
    public void EmailSecurityParsesSupportedModes(string configured, string expected)
    {
        var options = new EmailOptions { Security = configured, SmtpPort = 465, UseSsl = false };

        Assert.Equal(expected, options.ResolveSecurityMode());
    }

    [Theory]
    [InlineData(465, EmailSecurityModes.SslOnConnect)]
    [InlineData(587, EmailSecurityModes.StartTls)]
    [InlineData(25, EmailSecurityModes.Auto)]
    public void EmailSecurityUsesPortDefaultsWhenSecurityIsMissing(int port, string expected)
    {
        var options = new EmailOptions { SmtpPort = port, UseSsl = true };

        Assert.Equal(expected, options.ResolveSecurityMode());
    }

    [Fact]
    public void EmailSecurityKeepsUseSslCompatibilityWhenSecurityIsMissingForOtherPorts()
    {
        var options = new EmailOptions { SmtpPort = 2525, UseSsl = false };

        Assert.Equal(EmailSecurityModes.None, options.ResolveSecurityMode());
    }

    [Fact]
    public async Task QuoteNotificationServiceSkipsWithoutRequiredSmtpConfiguration()
    {
        var service = CreateService(new EmailOptions(), "jmateluna@jem-nexus.cl;fheim@jem-nexus.cl");

        var result = await service.SendNewQuoteRequestAsync(new QuoteRequest
        {
            CustomerName = "Cliente",
            CustomerEmail = "cliente@example.test",
            CustomerPhone = "+569",
            Message = "Cotizar",
            CreatedAt = DateTimeOffset.UtcNow
        });

        Assert.False(result.Success);
        Assert.True(result.Skipped);
        Assert.Equal("smtp_configuration_missing", result.ErrorCode);
        Assert.Equal(2, result.RecipientsCount);
        Assert.DoesNotContain("password", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task QuoteNotificationTestSkipsWhenRecipientsAreMissing()
    {
        var service = CreateService(new EmailOptions
        {
            SmtpHost = "jem-nexus.cl",
            SmtpPort = 465,
            FromAddress = "notificaciones@jem-nexus.cl",
            Password = "secret-password",
            Security = EmailSecurityModes.SslOnConnect
        }, recipients: string.Empty);

        var result = await service.SendTestNotificationAsync();

        Assert.True(result.Skipped);
        Assert.Equal("smtp_configuration_missing", result.ErrorCode);
        Assert.Equal(0, result.RecipientsCount);
        Assert.Equal("jem-nexus.cl", result.SmtpHost);
        Assert.Equal(465, result.SmtpPort);
        Assert.Equal(EmailSecurityModes.SslOnConnect, result.SecurityMode);
        Assert.DoesNotContain("secret-password", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    private static SmtpQuoteNotificationService CreateService(EmailOptions emailOptions, string recipients) => new(
        OptionsFactory.Create(emailOptions),
        OptionsFactory.Create(new QuoteNotificationOptions { Recipients = recipients }),
        OptionsFactory.Create(new FrontendOptions { BaseUrl = "https://jem-nexus.cl" }),
        NullLogger<SmtpQuoteNotificationService>.Instance);
}
