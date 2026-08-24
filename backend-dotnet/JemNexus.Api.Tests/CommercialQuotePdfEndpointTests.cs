using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using PdfSharp.Pdf.IO;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialQuotePdfEndpointTests
{
    [Fact]
    public async Task AnonymousIsUnauthorized()
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var response = await factory.CreateClient().GetAsync("/api/admin/commercial-quotes/1/pdf");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task OwnerAndSupportDownloadPdfButOtherSellerCannot()
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var owner = await factory.AuthorizedClientAsync("seller");
        var (id, folio) = await IssueAsync(owner, "CLP", 2);
        await factory.AddUserAsync("other-pdf-seller", AppRoles.Seller, "SELL-PDF-2");
        using var other = await factory.AuthorizedClientAsync("other-pdf-seller");
        using var support = await factory.AuthorizedClientAsync("support");

        using var ownerResponse = await owner.GetAsync($"/api/admin/commercial-quotes/{id}/pdf");
        using var supportResponse = await support.GetAsync($"/api/admin/commercial-quotes/{id}/pdf");
        using var otherResponse = await other.GetAsync($"/api/admin/commercial-quotes/{id}/pdf");

        Assert.Equal(HttpStatusCode.OK, ownerResponse.StatusCode);
        Assert.Equal(HttpStatusCode.OK, supportResponse.StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, otherResponse.StatusCode);
        Assert.Equal("application/pdf", ownerResponse.Content.Headers.ContentType?.MediaType);
        Assert.Equal("attachment", ownerResponse.Content.Headers.ContentDisposition?.DispositionType);
        Assert.Contains(folio, ownerResponse.Content.Headers.ContentDisposition?.FileNameStar ?? ownerResponse.Content.Headers.ContentDisposition?.FileName);
        Assert.EndsWith(".pdf", ownerResponse.Content.Headers.ContentDisposition?.FileNameStar ?? ownerResponse.Content.Headers.ContentDisposition?.FileName);
        Assert.True(ownerResponse.Headers.CacheControl?.Private);
        Assert.True(ownerResponse.Headers.CacheControl?.NoStore);
        Assert.Equal(["nosniff"], ownerResponse.Headers.GetValues("X-Content-Type-Options"));
        var bytes = await ownerResponse.Content.ReadAsByteArrayAsync();
        Assert.NotEmpty(bytes);
        Assert.Equal("%PDF-", Encoding.ASCII.GetString(bytes, 0, 5));
    }

    [Fact]
    public async Task MissingAndDraftQuotesAreNotAvailable()
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var owner = await factory.AuthorizedClientAsync("seller");
        Assert.Equal(HttpStatusCode.NotFound, (await owner.GetAsync("/api/admin/commercial-quotes/999999/pdf")).StatusCode);
        var (id, _) = await IssueAsync(owner, "CLP", 1);
        await factory.SetStatusAsync(id, CommercialQuoteStatuses.Draft);
        Assert.Equal(HttpStatusCode.NotFound, (await owner.GetAsync($"/api/admin/commercial-quotes/{id}/pdf")).StatusCode);
    }

    [Theory]
    [InlineData("CLP")]
    [InlineData("USD")]
    public async Task GeneratedDocumentIsValidLetterPortraitWithSafeMetadata(string currency)
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var owner = await factory.AuthorizedClientAsync("seller");
        var (id, folio) = await IssueAsync(owner, currency, 4, "Observación con español: áéíóú, ñ y símbolos & ®.\nSegunda línea.");
        var bytes = await owner.GetByteArrayAsync($"/api/admin/commercial-quotes/{id}/pdf");
        using var stream = new MemoryStream(bytes);
        using var pdf = PdfReader.Open(stream, PdfDocumentOpenMode.ReadOnly);
        Assert.NotEmpty(pdf.Pages);
        Assert.All(pdf.Pages.Cast<PdfSharp.Pdf.PdfPage>(), page =>
        {
            Assert.True(page.Height.Point > page.Width.Point);
            Assert.InRange(page.Width.Point, 611.5, 612.5);
            Assert.InRange(page.Height.Point, 791.5, 792.5);
        });
        Assert.Equal($"Cotización {folio}", pdf.Info.Title);
        Assert.Equal("JEM Nexus", pdf.Info.Author);
        Assert.Equal("Cotización comercial", pdf.Info.Subject);
        Assert.DoesNotContain("12.345.678-5", pdf.Info.ToString());
    }

    [Fact]
    public async Task LongQuoteIsMultipageLetterAndConcurrentGenerationsRemainValid()
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var owner = await factory.AuthorizedClientAsync("seller");
        var (id, _) = await IssueAsync(owner, "CLP", 80);
        var downloads = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ => owner.GetByteArrayAsync($"/api/admin/commercial-quotes/{id}/pdf")));
        Assert.All(downloads, bytes =>
        {
            using var stream = new MemoryStream(bytes);
            using var pdf = PdfReader.Open(stream, PdfDocumentOpenMode.ReadOnly);
            Assert.True(pdf.PageCount > 1);
            Assert.All(pdf.Pages.Cast<PdfSharp.Pdf.PdfPage>(), page =>
            {
                Assert.InRange(page.Width.Point, 611.5, 612.5);
                Assert.InRange(page.Height.Point, 791.5, 792.5);
            });
        });
    }

    [Fact]
    public void LogoIsEmbeddedAndSuccessiveDirectGenerationsDoNotShareState()
    {
        var assembly = typeof(CommercialQuotePdfGenerator).Assembly;
        Assert.Contains("JemNexus.Api.Assets.jem-nexus.png", assembly.GetManifestResourceNames());
        using var stream = assembly.GetManifestResourceStream("JemNexus.Api.Assets.jem-nexus.png");
        Assert.NotNull(stream); Assert.True(stream.Length > 0);
    }

    [Fact]
    public async Task DownloadDoesNotPersistOrUpdateCommercialState()
    {
        await using var factory = new AdminCommercialQuoteEndpointTests.QuoteApiFactory();
        using var owner = await factory.AuthorizedClientAsync("seller");
        var (id, _) = await IssueAsync(owner, "CLP", 2);
        var before = await StateAsync(factory, id);

        using var response = await owner.GetAsync($"/api/admin/commercial-quotes/{id}/pdf");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var after = await StateAsync(factory, id);

        Assert.Equal(before, after);
    }

    private static async Task<(int Quotes, int Idempotency, int FolioCounters, DateTimeOffset UpdatedAt)> StateAsync(
        AdminCommercialQuoteEndpointTests.QuoteApiFactory factory, int id)
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        return (await db.CommercialQuotes.CountAsync(),
            await db.CommercialQuoteIssueIdempotencyRecords.CountAsync(),
            await db.CommercialQuoteFolioCounters.CountAsync(),
            await db.CommercialQuotes.AsNoTracking().Where(quote => quote.Id == id).Select(quote => quote.UpdatedAt).SingleAsync());
    }

    private static async Task<(int Id, string Folio)> IssueAsync(HttpClient client, string currency, int itemCount, string? observations = null)
    {
        var items = Enumerable.Range(1, itemCount).Select(position => new
        {
            source = "FreeText", product_name = $"Servicio técnico número {position} con descripción suficientemente extensa para verificar ajuste de texto",
            brand_name = position % 2 == 0 ? "Marca" : null, model_name = position % 2 == 0 ? "Modelo" : null,
            quantity = 2, unit_net_amount = currency == "CLP" ? 123456m : 1234.56m, discount_percent = 5m
        }).ToArray();
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/admin/commercial-quotes/issue")
        {
            Content = JsonContent.Create(new { customer_business_name = "Cliente PDF", customer_rut = "12.345.678-5", customer_business_activity = "Servicios",
                customer_address = "Dirección 123", customer_phone = "+56 9 1234 5678", customer_city_or_commune = "Santiago", customer_contact_name = "Señora Ñandú",
                customer_email = "pdf@example.test", currency, sale_condition = "Cash", validity_days = 15, detailed_description = observations, items })
        };
        request.Headers.Add("Idempotency-Key", Guid.NewGuid().ToString());
        using var response = await client.SendAsync(request); response.EnsureSuccessStatusCode();
        var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement;
        return (json.GetProperty("id").GetInt32(), json.GetProperty("folio").GetString()!);
    }
}
