namespace JemNexus.Api.Models;

public sealed class HomeSectionItem
{
    public int Id { get; set; }
    public string Section { get; set; } = HomeSections.MachineryPromotions;
    public int Position { get; set; } = 1;
    public int ProductId { get; set; }
    public Product Product { get; set; } = null!;
    public bool IsActive { get; set; } = true;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public AppUser? CreatedBy { get; set; }
    public int? UpdatedById { get; set; }
    public AppUser? UpdatedBy { get; set; }
}

public static class HomeSections
{
    public const string MachineryPromotions = "machinery_promotions";
    public const string SparePartsOffers = "spare_parts_offers";
    public const string RepairServices = "repair_services";
}
