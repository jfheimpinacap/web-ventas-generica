namespace JemNexus.Api.Models;

public sealed class Supplier
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string ContactName { get; set; } = string.Empty;
    public string Phone { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string Notes { get; set; } = string.Empty;
    public bool IsActive { get; set; } = true;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public int? UpdatedById { get; set; }
    public ICollection<Product> Products { get; set; } = new List<Product>();
}
