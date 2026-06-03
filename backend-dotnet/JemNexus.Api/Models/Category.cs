namespace JemNexus.Api.Models;

public sealed class Category
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Slug { get; set; } = string.Empty;
    public int? ParentId { get; set; }
    public Category? Parent { get; set; }
    public ICollection<Category> Children { get; set; } = new List<Category>();
    public string Description { get; set; } = string.Empty;
    public bool IsActive { get; set; } = true;
    public int Order { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public int? UpdatedById { get; set; }
    public ICollection<Product> Products { get; set; } = new List<Product>();
}
