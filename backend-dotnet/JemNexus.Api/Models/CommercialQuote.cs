namespace JemNexus.Api.Models;

public sealed class CommercialQuote
{
    public int Id { get; set; }
    public string Status { get; set; } = CommercialQuoteStatuses.Draft;
    public string Currency { get; set; } = CommercialQuoteCurrencies.Clp;
    public string SaleCondition { get; set; } = CommercialQuoteSaleConditions.Cash;
    public int ValidityDays { get; set; } = 15;
    public string? DetailedDescription { get; set; }
    public decimal TaxRatePercent { get; private set; } = CommercialQuoteRules.TaxRatePercent;
    public int? CustomerProfileId { get; set; }
    public CustomerProfile? CustomerProfile { get; set; }
    public string CustomerBusinessName { get; set; } = string.Empty;
    public string CustomerRut { get; set; } = string.Empty;
    public string CustomerBusinessActivity { get; set; } = string.Empty;
    public string CustomerAddress { get; set; } = string.Empty;
    public string CustomerPhone { get; set; } = string.Empty;
    public string CustomerCityOrCommune { get; set; } = string.Empty;
    public string CustomerContactName { get; set; } = string.Empty;
    public string? CustomerEmail { get; set; }
    public int ResponsibleSellerId { get; set; }
    public AppUser ResponsibleSeller { get; set; } = null!;
    public string ResponsibleSellerName { get; set; } = string.Empty;
    public string ResponsibleSellerCode { get; set; } = string.Empty;
    public decimal NetAmount { get; private set; }
    public decimal TaxAmount { get; private set; }
    public decimal TotalAmount { get; private set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public ICollection<CommercialQuoteItem> Items { get; set; } = new List<CommercialQuoteItem>();

    internal void SetTotals(decimal netAmount, decimal taxAmount, decimal totalAmount)
    {
        TaxRatePercent = CommercialQuoteRules.TaxRatePercent;
        NetAmount = netAmount;
        TaxAmount = taxAmount;
        TotalAmount = totalAmount;
    }
}

public static class CommercialQuoteStatuses { public const string Draft = "Draft"; }
public static class CommercialQuoteCurrencies { public const string Clp = "CLP"; public const string Usd = "USD"; }
public static class CommercialQuoteSaleConditions { public const string Cash = "Cash"; public const string Credit30Days = "Credit30Days"; }
public static class CommercialQuoteItemOrigins { public const string Catalog = "Catalog"; public const string FreeText = "FreeText"; }
public static class CommercialQuoteRules
{
    public const decimal TaxRatePercent = 19.00m;
    public const int DefaultValidityDays = 15;
    public const int DetailedDescriptionMaxLength = 1000;
}
