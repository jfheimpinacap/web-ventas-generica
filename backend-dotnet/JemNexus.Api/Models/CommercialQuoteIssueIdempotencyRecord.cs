namespace JemNexus.Api.Models;

public sealed class CommercialQuoteIssueIdempotencyRecord
{
    public int ResponsibleSellerId { get; set; }
    public AppUser ResponsibleSeller { get; set; } = null!;
    public Guid IdempotencyKey { get; set; }
    public string RequestFingerprint { get; set; } = string.Empty;
    public int CommercialQuoteId { get; set; }
    public CommercialQuote CommercialQuote { get; set; } = null!;
    public DateTimeOffset CreatedAt { get; set; }
}
