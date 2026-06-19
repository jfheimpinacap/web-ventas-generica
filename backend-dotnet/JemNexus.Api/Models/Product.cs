namespace JemNexus.Api.Models;

public sealed class Product
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Slug { get; set; } = string.Empty;
    public int CategoryId { get; set; }
    public Category Category { get; set; } = null!;
    public int? BrandId { get; set; }
    public Brand? Brand { get; set; }
    public int? SupplierId { get; set; }
    public Supplier? Supplier { get; set; }
    public string ProductType { get; set; } = ProductTypes.Machinery;
    public string Condition { get; set; } = ProductConditions.NotApplicable;
    public string ShortDescription { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Model { get; set; } = string.Empty;
    public string Sku { get; set; } = string.Empty;
    public int? Year { get; set; }
    public int? HoursMeter { get; set; }
    public decimal? Price { get; set; }
    public string PriceCurrency { get; set; } = ProductPriceCurrencies.Clp;
    public string PriceTaxMode { get; set; } = ProductPriceTaxModes.PlusVat;
    public bool PriceVisible { get; set; } = true;
    public string StockStatus { get; set; } = StockStatuses.OnRequest;
    public bool IsFeatured { get; set; }
    public bool IsPublished { get; set; } = true;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public AppUser? CreatedBy { get; set; }
    public int? UpdatedById { get; set; }
    public AppUser? UpdatedBy { get; set; }
    public ICollection<ProductImage> Images { get; set; } = new List<ProductImage>();
    public ICollection<ProductSpec> Specs { get; set; } = new List<ProductSpec>();
    public ICollection<Promotion> Promotions { get; set; } = new List<Promotion>();
    public ICollection<HomeSectionItem> HomeSectionItems { get; set; } = new List<HomeSectionItem>();
    public ICollection<QuoteRequest> QuoteRequests { get; set; } = new List<QuoteRequest>();
}

public static class ProductTypes
{
    public const string Machinery = "machinery";
    public const string SparePart = "spare_part";
    public const string Service = "service";
}

public static class ProductConditions
{
    public const string New = "new";
    public const string Used = "used";
    public const string Refurbished = "refurbished";
    public const string NotApplicable = "not_applicable";
}

public static class StockStatuses
{
    public const string Available = "available";
    public const string OnRequest = "on_request";
    public const string Sold = "sold";
    public const string Reserved = "reserved";
}


public static class ProductPriceCurrencies
{
    public const string Clp = "CLP";
    public const string Usd = "USD";
}

public static class ProductPriceTaxModes
{
    public const string PlusVat = "plus_vat";
    public const string VatIncluded = "vat_included";
}
