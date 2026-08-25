using System.Net.Mail;
using JemNexus.Api.Models;

namespace JemNexus.Api.Services;

public static class CommercialQuoteCalculator
{
    public static void Calculate(CommercialQuote quote)
    {
        ArgumentNullException.ThrowIfNull(quote);
        ValidateQuote(quote);
        var decimals = quote.Currency == CommercialQuoteCurrencies.Clp ? 0 : 2;
        decimal net = 0m;
        var positions = new HashSet<int>();

        foreach (var item in quote.Items)
        {
            ValidateItem(item, positions);
            var finalUnit = Round(item.UnitNetAmount * (1m - item.DiscountPercent / 100m), decimals);
            var line = Round(item.Quantity * finalUnit, decimals);
            item.SetCalculatedAmounts(finalUnit, line);
            net += line;
        }

        net = Round(net, decimals);
        var tax = Round(net * CommercialQuoteRules.TaxRatePercent / 100m, decimals);
        quote.SetTotals(net, tax, Round(net + tax, decimals));
    }

    private static void ValidateQuote(CommercialQuote quote)
    {
        if (quote.Status != CommercialQuoteStatuses.Draft) throw new ArgumentException("Only Draft is supported.");
        if (quote.Currency is not (CommercialQuoteCurrencies.Clp or CommercialQuoteCurrencies.Usd)) throw new ArgumentException("Unsupported currency.");
        if (!CommercialQuoteSaleConditions.IsAllowed(quote.SaleCondition)) throw new ArgumentException("Unsupported sale condition.");
        if (!CommercialQuoteRules.IsAllowedValidityDays(quote.ValidityDays)) throw new ArgumentException("Unsupported validity days.");
        if (quote.DetailedDescription?.Length > CommercialQuoteRules.DetailedDescriptionMaxLength) throw new ArgumentException("Detailed description is too long.");
        Require(quote.CustomerBusinessName, nameof(quote.CustomerBusinessName));
        Require(quote.CustomerBusinessActivity, nameof(quote.CustomerBusinessActivity));
        Require(quote.CustomerAddress, nameof(quote.CustomerAddress));
        Require(quote.CustomerPhone, nameof(quote.CustomerPhone));
        Require(quote.CustomerCityOrCommune, nameof(quote.CustomerCityOrCommune));
        Require(quote.CustomerContactName, nameof(quote.CustomerContactName));
        Require(quote.ResponsibleSellerName, nameof(quote.ResponsibleSellerName));
        Require(quote.ResponsibleSellerCode, nameof(quote.ResponsibleSellerCode));
        if (!ChileanRut.TryNormalize(quote.CustomerRut, out var rut)) throw new ArgumentException(ChileanRut.InvalidMessage);
        quote.CustomerRut = rut;
        quote.CustomerEmail = NormalizeEmail(quote.CustomerEmail);
    }

    private static void ValidateItem(CommercialQuoteItem item, HashSet<int> positions)
    {
        if (item.Position <= 0) throw new ArgumentException("Position must be positive.");
        if (!positions.Add(item.Position)) throw new ArgumentException("Item positions must be unique.");
        if (item.Quantity <= 0) throw new ArgumentException("Quantity must be positive.");
        if (item.UnitNetAmount <= 0m) throw new ArgumentException("Unit net amount must be positive.");
        if (item.DiscountPercent is < 0m or > 100m) throw new ArgumentException("Discount must be between 0 and 100.");
        Require(item.ProductName, nameof(item.ProductName));
        if (item.Origin == CommercialQuoteItemOrigins.Catalog && item.ProductId is null) throw new ArgumentException("Catalog items require a product.");
        if (item.Origin == CommercialQuoteItemOrigins.FreeText && item.ProductId is not null) throw new ArgumentException("Free-text items cannot reference a product.");
        if (item.Origin is not (CommercialQuoteItemOrigins.Catalog or CommercialQuoteItemOrigins.FreeText)) throw new ArgumentException("Unsupported item origin.");
    }

    private static string? NormalizeEmail(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return null;
        var normalized = value.Trim();
        try { return new MailAddress(normalized).Address == normalized ? normalized : throw new FormatException(); }
        catch (FormatException) { throw new ArgumentException("Customer email is invalid."); }
    }

    private static decimal Round(decimal value, int decimals) => Math.Round(value, decimals, MidpointRounding.AwayFromZero);
    private static void Require(string? value, string name) { if (string.IsNullOrWhiteSpace(value)) throw new ArgumentException($"{name} is required."); }
}
