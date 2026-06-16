using JemNexus.Api.Models;
using JemNexus.Api.Validation;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialValidationTests
{
    [Theory]
    [InlineData(ProductTypes.Machinery, true)]
    [InlineData(ProductTypes.SparePart, true)]
    [InlineData(ProductTypes.Service, true)]
    [InlineData("invalid", false)]
    public void ProductTypesAreValidatedAgainstAllowedConstants(string value, bool expected)
    {
        Assert.Equal(expected, CommercialValidation.IsAllowedProductType(value));
    }

    [Theory]
    [InlineData(ProductConditions.New, true)]
    [InlineData(ProductConditions.Used, true)]
    [InlineData(ProductConditions.Refurbished, true)]
    [InlineData(ProductConditions.NotApplicable, true)]
    [InlineData("invalid", false)]
    public void ProductConditionsAreValidatedAgainstAllowedConstants(string value, bool expected)
    {
        Assert.Equal(expected, CommercialValidation.IsAllowedProductCondition(value));
    }

    [Theory]
    [InlineData(StockStatuses.Available, true)]
    [InlineData(StockStatuses.OnRequest, true)]
    [InlineData(StockStatuses.Sold, true)]
    [InlineData(StockStatuses.Reserved, true)]
    [InlineData("invalid", false)]
    public void StockStatusesAreValidatedAgainstAllowedConstants(string value, bool expected)
    {
        Assert.Equal(expected, CommercialValidation.IsAllowedStockStatus(value));
    }

    [Theory]
    [InlineData(QuoteStatuses.New, true)]
    [InlineData(QuoteStatuses.Contacted, true)]
    [InlineData(QuoteStatuses.Quoted, true)]
    [InlineData(QuoteStatuses.Closed, true)]
    [InlineData(QuoteStatuses.Discarded, true)]
    [InlineData("invalid", false)]
    public void QuoteStatusesAreValidatedAgainstAllowedConstants(string value, bool expected)
    {
        Assert.Equal(expected, CommercialValidation.IsAllowedQuoteStatus(value));
    }

    [Fact]
    public void ProductValidationCatchesCoreDjangoEquivalentRules()
    {
        var product = new Product
        {
            Name = " ",
            Slug = "",
            CategoryId = 0,
            ProductType = "invalid",
            Condition = "invalid",
            StockStatus = "invalid",
            Price = -1,
            Year = 1800,
            HoursMeter = -5
        };

        var errors = CommercialValidation.ValidateProduct(product);

        Assert.NotEmpty(errors);
        Assert.Contains(errors, error => error.Contains("Name", StringComparison.Ordinal));
        Assert.Contains(errors, error => error.Contains("Slug", StringComparison.Ordinal));
        Assert.Contains(errors, error => error.Contains("category", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("type", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("condition", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("stock", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("price", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("year", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("hours", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void QuoteValidationCatchesCoreDjangoEquivalentRules()
    {
        var quote = new QuoteRequest
        {
            CustomerName = "",
            CustomerEmail = "not-an-email",
            Message = new string('x', CommercialValidation.QuoteMessageMaxLength + 1),
            Status = "invalid",
            PreferredContactMethod = "invalid"
        };

        var errors = CommercialValidation.ValidateQuoteRequest(quote);

        Assert.NotEmpty(errors);
        Assert.Contains(errors, error => error.Contains("CustomerName", StringComparison.Ordinal));
        Assert.Contains(errors, error => error.Contains("email", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("message", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("status", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("contact", StringComparison.OrdinalIgnoreCase));
    }
}
