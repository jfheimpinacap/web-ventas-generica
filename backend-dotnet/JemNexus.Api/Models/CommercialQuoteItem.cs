namespace JemNexus.Api.Models;

public sealed class CommercialQuoteItem
{
    public int Id { get; set; }
    public int CommercialQuoteId { get; set; }
    public CommercialQuote CommercialQuote { get; set; } = null!;
    public int Position { get; set; }
    public string Origin { get; set; } = CommercialQuoteItemOrigins.FreeText;
    public int? ProductId { get; set; }
    public Product? Product { get; set; }
    public string ProductName { get; set; } = string.Empty;
    public string? BrandName { get; set; }
    public string? ModelName { get; set; }
    public int Quantity { get; set; }
    public decimal UnitNetAmount { get; set; }
    public decimal DiscountPercent { get; set; }
    public decimal FinalUnitNetAmount { get; private set; }
    public decimal LineNetAmount { get; private set; }

    internal void SetCalculatedAmounts(decimal finalUnitNetAmount, decimal lineNetAmount)
    {
        FinalUnitNetAmount = finalUnitNetAmount;
        LineNetAmount = lineNetAmount;
    }
}
