using System.Text.Json.Serialization;

namespace JemNexus.Api.Contracts.Admin;

public sealed record CommercialQuoteItemInput(
    string? Source,
    [property: JsonPropertyName("product_id")] int? ProductId,
    [property: JsonPropertyName("product_name")] string? ProductName,
    [property: JsonPropertyName("brand_name")] string? BrandName,
    [property: JsonPropertyName("model_name")] string? ModelName,
    int Quantity,
    [property: JsonPropertyName("unit_net_amount")] decimal UnitNetAmount,
    [property: JsonPropertyName("discount_percent")] decimal? DiscountPercent);

public abstract record CommercialQuoteInput(
    [property: JsonPropertyName("customer_profile_id")] int? CustomerProfileId,
    [property: JsonPropertyName("customer_business_name")] string? CustomerBusinessName,
    [property: JsonPropertyName("customer_rut")] string? CustomerRut,
    [property: JsonPropertyName("customer_business_activity")] string? CustomerBusinessActivity,
    [property: JsonPropertyName("customer_address")] string? CustomerAddress,
    [property: JsonPropertyName("customer_phone")] string? CustomerPhone,
    [property: JsonPropertyName("customer_city_or_commune")] string? CustomerCityOrCommune,
    [property: JsonPropertyName("customer_contact_name")] string? CustomerContactName,
    [property: JsonPropertyName("customer_email")] string? CustomerEmail,
    string? Currency,
    [property: JsonPropertyName("sale_condition")] string? SaleCondition,
    [property: JsonPropertyName("validity_days")] int? ValidityDays,
    [property: JsonPropertyName("detailed_description")] string? DetailedDescription,
    IReadOnlyList<CommercialQuoteItemInput>? Items);

public sealed record CommercialQuoteIssueRequest(int? CustomerProfileId, string? CustomerBusinessName, string? CustomerRut, string? CustomerBusinessActivity, string? CustomerAddress, string? CustomerPhone, string? CustomerCityOrCommune, string? CustomerContactName, string? CustomerEmail, string? Currency, string? SaleCondition, int? ValidityDays, string? DetailedDescription, IReadOnlyList<CommercialQuoteItemInput>? Items)
    : CommercialQuoteInput(CustomerProfileId, CustomerBusinessName, CustomerRut, CustomerBusinessActivity, CustomerAddress, CustomerPhone, CustomerCityOrCommune, CustomerContactName, CustomerEmail, Currency, SaleCondition, ValidityDays, DetailedDescription, Items);

public sealed record CommercialQuoteItemResponse(int Id, int Position, string Source, int? ProductId, string ProductName, string? BrandName, string? ModelName, int Quantity, decimal UnitNetAmount, decimal DiscountPercent, decimal FinalUnitNetAmount, decimal LineNetAmount);
public sealed record CommercialQuoteSummaryResponse(int Id, string Status, string? Folio, DateTime? IssuedAt, DateOnly? IssuedOn, string Currency, string CustomerBusinessName, string CustomerRut, string CustomerContactName, string SellerName, string SellerCode, decimal NetAmount, decimal TaxAmount, decimal TotalAmount, int ItemCount, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt);
public sealed record CommercialQuoteDetailResponse(int Id, string Status, string? Folio, DateTime? IssuedAt, DateOnly? IssuedOn, int? CustomerProfileId, string CustomerBusinessName, string CustomerRut, string CustomerBusinessActivity, string CustomerAddress, string CustomerPhone, string CustomerCityOrCommune, string CustomerContactName, string? CustomerEmail, string SellerName, string SellerCode, string Currency, string SaleCondition, int ValidityDays, string? DetailedDescription, decimal TaxRatePercent, decimal NetAmount, decimal TaxAmount, decimal TotalAmount, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt, IReadOnlyList<CommercialQuoteItemResponse> Items);
public sealed record CommercialQuotePageResponse(IReadOnlyList<CommercialQuoteSummaryResponse> Results, int Page, int PageSize, int Count);
