using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialQuoteCalculatorTests
{
    [Theory]
    [InlineData("CLP", 1000, 0, 2, 1000, 2000, 380, 2380)]
    [InlineData("CLP", 1001, 12.50, 3, 876, 2628, 499, 3127)]
    [InlineData("CLP", 5, 10, 1, 5, 5, 1, 6)]
    [InlineData("USD", 10.25, 0, 2, 10.25, 20.50, 3.90, 24.40)]
    [InlineData("USD", 10.25, 12.50, 3, 8.97, 26.91, 5.11, 32.02)]
    [InlineData("USD", 1.005, 0, 1, 1.01, 1.01, .19, 1.20)]
    [InlineData("USD", 99, 100, 4, 0, 0, 0, 0)]
    public void CalculatesExactAmounts(string currency, decimal unit, decimal discount, int quantity, decimal finalUnit, decimal net, decimal tax, decimal total)
    {
        var quote = ValidQuote(currency); quote.Items.Add(Item(1, quantity, unit, discount)); CommercialQuoteCalculator.Calculate(quote);
        Assert.Equal(finalUnit, quote.Items.Single().FinalUnitNetAmount); Assert.Equal(net, quote.NetAmount); Assert.Equal(tax, quote.TaxAmount); Assert.Equal(total, quote.TotalAmount); Assert.Equal(19m, quote.TaxRatePercent);
    }

    [Theory]
    [InlineData("CLP", 1000, 14.3, 2857, 543, 3400)]
    [InlineData("USD", 10, 14.4, 28.56, 5.43, 33.99)]
    public void SumsMultipleItems(string currency, decimal unitNetAmount, decimal secondItemDiscount, decimal net, decimal tax, decimal total)
    { var q = ValidQuote(currency); q.Items.Add(Item(1, 2, unitNetAmount, 0)); q.Items.Add(Item(2, 1, unitNetAmount, secondItemDiscount)); CommercialQuoteCalculator.Calculate(q); Assert.Equal(net, q.NetAmount); Assert.Equal(tax, q.TaxAmount); Assert.Equal(total, q.TotalAmount); }

    [Fact] public void EmptyDraftHasZeroTotals() { var q = ValidQuote(); CommercialQuoteCalculator.Calculate(q); Assert.Equal(0m, q.TotalAmount); }
    [Fact] public void CalculationIsDeterministicAndDefaultDiscountIsZero() { var q = ValidQuote(); q.Items.Add(Item(1, 1, 10)); CommercialQuoteCalculator.Calculate(q); var first = q.TotalAmount; CommercialQuoteCalculator.Calculate(q); Assert.Equal(first, q.TotalAmount); }

    [Theory]
    [InlineData(0, 1, 1, 0)] [InlineData(-1, 1, 1, 0)] [InlineData(1, 0, 1, 0)] [InlineData(1, -1, 1, 0)] [InlineData(1, 1, 0, 0)] [InlineData(1, 1, -1, 0)] [InlineData(1, 1, 1, -1)] [InlineData(1, 1, 1, 101)]
    public void InvalidItemNumbersAreRejected(int position, int quantity, decimal unit, decimal discount) { var q = ValidQuote(); q.Items.Add(Item(position, quantity, unit, discount)); Assert.Throws<ArgumentException>(() => CommercialQuoteCalculator.Calculate(q)); }
    [Fact] public void DuplicatePositionsAreRejected() { var q = ValidQuote(); q.Items.Add(Item(1)); q.Items.Add(Item(1)); Assert.Throws<ArgumentException>(() => CommercialQuoteCalculator.Calculate(q)); }
    [Fact] public void FreeTextRequiresName() { var q = ValidQuote(); q.Items.Add(Item(1)); q.Items.Single().ProductName = " "; Assert.Throws<ArgumentException>(() => CommercialQuoteCalculator.Calculate(q)); }
    [Fact] public void UnsupportedCurrencyIsRejected() { var q = ValidQuote("EUR"); Assert.Throws<ArgumentException>(() => CommercialQuoteCalculator.Calculate(q)); }

    internal static CommercialQuote ValidQuote(string currency = "CLP") => new() { Currency = currency, CustomerBusinessName = "Cliente", CustomerRut = "12345678-5", CustomerBusinessActivity = "Servicios", CustomerAddress = "Calle 1", CustomerPhone = "123", CustomerCityOrCommune = "Santiago", CustomerContactName = "Contacto", ResponsibleSellerId = 1, ResponsibleSellerName = "Vendedor", ResponsibleSellerCode = "VEN-0001" };
    internal static CommercialQuoteItem Item(int position, int quantity = 1, decimal unit = 100m, decimal discount = 0m) => new() { Position = position, Quantity = quantity, UnitNetAmount = unit, DiscountPercent = discount, ProductName = "Servicio" };
}
