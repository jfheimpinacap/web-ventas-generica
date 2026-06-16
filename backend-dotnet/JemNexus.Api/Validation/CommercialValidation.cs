using System.Net.Mail;
using JemNexus.Api.Models;

namespace JemNexus.Api.Validation;

public static class CommercialValidation
{
    public const int QuoteMessageMaxLength = 2000;
    public const int MinReasonableYear = 1900;
    public const int MaxFutureYearOffset = 1;

    public static readonly string[] AllowedProductTypes =
    [
        ProductTypes.Machinery,
        ProductTypes.SparePart,
        ProductTypes.Service
    ];

    public static readonly string[] AllowedProductConditions =
    [
        ProductConditions.New,
        ProductConditions.Used,
        ProductConditions.Refurbished,
        ProductConditions.NotApplicable
    ];

    public static readonly string[] AllowedStockStatuses =
    [
        StockStatuses.Available,
        StockStatuses.OnRequest,
        StockStatuses.Sold,
        StockStatuses.Reserved
    ];

    public static readonly string[] AllowedQuoteStatuses =
    [
        QuoteStatuses.New,
        QuoteStatuses.Contacted,
        QuoteStatuses.Quoted,
        QuoteStatuses.Closed,
        QuoteStatuses.Discarded
    ];

    public static readonly string[] AllowedPreferredContactMethods =
    [
        string.Empty,
        PreferredContactMethods.Phone,
        PreferredContactMethods.Email,
        PreferredContactMethods.WhatsApp
    ];

    public static bool IsAllowedProductType(string? value) => IsAllowed(value, AllowedProductTypes);
    public static bool IsAllowedProductCondition(string? value) => IsAllowed(value, AllowedProductConditions);
    public static bool IsAllowedStockStatus(string? value) => IsAllowed(value, AllowedStockStatuses);
    public static bool IsAllowedQuoteStatus(string? value) => IsAllowed(value, AllowedQuoteStatuses);
    public static bool IsAllowedPreferredContactMethod(string? value) => IsAllowed(value, AllowedPreferredContactMethods);

    public static IReadOnlyList<string> ValidateProduct(Product product)
    {
        var errors = new List<string>();

        AddRequired(errors, nameof(product.Name), product.Name);
        AddRequired(errors, nameof(product.Slug), product.Slug);

        if (product.CategoryId <= 0)
        {
            errors.Add("Product category is required.");
        }

        if (!IsAllowedProductType(product.ProductType))
        {
            errors.Add("Product type is not allowed.");
        }

        if (!IsAllowedProductCondition(product.Condition))
        {
            errors.Add("Product condition is not allowed.");
        }

        if (!IsAllowedStockStatus(product.StockStatus))
        {
            errors.Add("Product stock status is not allowed.");
        }

        if (product.Price is < 0)
        {
            errors.Add("Product price cannot be negative.");
        }

        var maxYear = DateTimeOffset.UtcNow.Year + MaxFutureYearOffset;
        if (product.Year is not null && (product.Year < MinReasonableYear || product.Year > maxYear))
        {
            errors.Add($"Product year must be between {MinReasonableYear} and {maxYear}.");
        }

        if (product.HoursMeter is < 0)
        {
            errors.Add("Product hours meter cannot be negative.");
        }

        return errors;
    }

    public static IReadOnlyList<string> ValidateQuoteRequest(QuoteRequest quote)
    {
        var errors = new List<string>();

        AddRequired(errors, nameof(quote.CustomerName), quote.CustomerName);
        AddRequired(errors, nameof(quote.Message), quote.Message);

        if (quote.Message.Length > QuoteMessageMaxLength)
        {
            errors.Add($"Quote message cannot exceed {QuoteMessageMaxLength} characters.");
        }

        if (!string.IsNullOrWhiteSpace(quote.CustomerEmail) && !IsValidEmail(quote.CustomerEmail))
        {
            errors.Add("Quote customer email format is invalid.");
        }

        if (!IsAllowedQuoteStatus(quote.Status))
        {
            errors.Add("Quote status is not allowed.");
        }

        if (!IsAllowedPreferredContactMethod(quote.PreferredContactMethod))
        {
            errors.Add("Quote preferred contact method is not allowed.");
        }

        return errors;
    }

    public static IReadOnlyList<string> ValidateProductImage(ProductImage image)
    {
        var errors = new List<string>();

        AddRequired(errors, nameof(image.Image), image.Image);
        if (image.Order < 0)
        {
            errors.Add("Product image order cannot be negative.");
        }

        return errors;
    }

    public static IReadOnlyList<string> ValidateProductSpec(ProductSpec spec)
    {
        var errors = new List<string>();

        AddRequired(errors, nameof(spec.Key), spec.Key);
        AddRequired(errors, nameof(spec.Value), spec.Value);
        if (spec.Order < 0)
        {
            errors.Add("Product spec order cannot be negative.");
        }

        return errors;
    }

    private static bool IsAllowed(string? value, IReadOnlyCollection<string> allowedValues)
    {
        return value is not null && allowedValues.Contains(value, StringComparer.Ordinal);
    }

    private static void AddRequired(ICollection<string> errors, string fieldName, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            errors.Add($"{fieldName} is required.");
        }
    }

    private static bool IsValidEmail(string email)
    {
        try
        {
            _ = new MailAddress(email);
            return true;
        }
        catch (FormatException)
        {
            return false;
        }
    }
}
