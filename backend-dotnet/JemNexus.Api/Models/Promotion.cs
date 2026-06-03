namespace JemNexus.Api.Models;

public sealed class Promotion
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Subtitle { get; set; } = string.Empty;
    public int? ProductId { get; set; }
    public Product? Product { get; set; }
    public string? Image { get; set; }
    public string ButtonText { get; set; } = string.Empty;
    public string ButtonUrl { get; set; } = string.Empty;
    public bool IsActive { get; set; } = true;
    public int Order { get; set; }
    public DateTimeOffset? StartsAt { get; set; }
    public DateTimeOffset? EndsAt { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public AppUser? CreatedBy { get; set; }
    public int? UpdatedById { get; set; }
    public AppUser? UpdatedBy { get; set; }
}
