namespace JemNexus.Api.Models;

public sealed class QuoteRequest
{
    public int Id { get; set; }
    public int? ProductId { get; set; }
    public Product? Product { get; set; }
    public string CustomerName { get; set; } = string.Empty;
    public string CustomerPhone { get; set; } = string.Empty;
    public string CustomerEmail { get; set; } = string.Empty;
    public string CompanyName { get; set; } = string.Empty;
    public string City { get; set; } = string.Empty;
    public string PreferredContactMethod { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string Status { get; set; } = QuoteStatuses.New;
    public string InternalNotes { get; set; } = string.Empty;
    public string SellerResponse { get; set; } = string.Empty;
    public DateTimeOffset? ContactedAt { get; set; }
    public DateTimeOffset? QuotedAt { get; set; }
    public DateTimeOffset? ClosedAt { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public int? UpdatedById { get; set; }
}

public static class QuoteStatuses
{
    public const string New = "new";
    public const string Contacted = "contacted";
    public const string Quoted = "quoted";
    public const string Closed = "closed";
    public const string Discarded = "discarded";
}

public static class PreferredContactMethods
{
    public const string Phone = "phone";
    public const string Email = "email";
    public const string WhatsApp = "whatsapp";
}
