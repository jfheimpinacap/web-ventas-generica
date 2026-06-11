using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace JemNexus.Api.Dtos;

public sealed record CategoryWriteDto(
    [property: StringLength(120)] string? Name,
    [property: StringLength(140)] string? Slug,
    int? Parent,
    [property: JsonPropertyName("parent_id")] int? ParentId,
    string? Description,
    [property: JsonPropertyName("is_active")] bool? IsActive,
    int? Order);

public sealed record BrandWriteDto(
    [property: StringLength(120)] string? Name,
    [property: StringLength(140)] string? Slug,
    [property: StringLength(500)] string? Logo,
    string? Description,
    [property: JsonPropertyName("is_active")] bool? IsActive);

public sealed record SupplierWriteDto(
    [property: StringLength(160)] string? Name,
    [property: JsonPropertyName("contact_name"), StringLength(160)] string? ContactName,
    [property: StringLength(40)] string? Phone,
    [property: StringLength(254)] string? Email,
    string? Notes,
    [property: JsonPropertyName("is_active")] bool? IsActive);

public sealed record PromotionWriteDto(
    [property: StringLength(180)] string? Title,
    [property: StringLength(280)] string? Subtitle,
    int? Product,
    [property: JsonPropertyName("product_id")] int? ProductId,
    [property: StringLength(500)] string? Image,
    [property: JsonPropertyName("button_text"), StringLength(80)] string? ButtonText,
    [property: JsonPropertyName("button_url"), StringLength(2048)] string? ButtonUrl,
    [property: JsonPropertyName("is_active")] bool? IsActive,
    int? Order,
    [property: JsonPropertyName("starts_at")] DateTimeOffset? StartsAt,
    [property: JsonPropertyName("ends_at")] DateTimeOffset? EndsAt);

public sealed record ProductWriteDto(
    [property: StringLength(220)] string? Name,
    [property: StringLength(240)] string? Slug,
    int? Category,
    [property: JsonPropertyName("category_id")] int? CategoryId,
    int? Brand,
    [property: JsonPropertyName("brand_id")] int? BrandId,
    int? Supplier,
    [property: JsonPropertyName("supplier_id")] int? SupplierId,
    [property: JsonPropertyName("product_type"), StringLength(20)] string? ProductType,
    [property: StringLength(20)] string? Condition,
    [property: JsonPropertyName("short_description"), StringLength(280)] string? ShortDescription,
    string? Description,
    [property: StringLength(120)] string? Model,
    [property: StringLength(120)] string? Sku,
    int? Year,
    [property: JsonPropertyName("hours_meter")] int? HoursMeter,
    decimal? Price,
    [property: JsonPropertyName("price_visible")] bool? PriceVisible,
    [property: JsonPropertyName("stock_status"), StringLength(20)] string? StockStatus,
    [property: JsonPropertyName("is_featured")] bool? IsFeatured,
    [property: JsonPropertyName("is_published")] bool? IsPublished);

public sealed record ProductSpecWriteDto(
    int? Product,
    [property: JsonPropertyName("product_id")] int? ProductId,
    [property: StringLength(120)] string? Name,
    [property: StringLength(120)] string? Key,
    [property: StringLength(220)] string? Value,
    [property: StringLength(40)] string? Unit,
    int? Order);

public sealed record QuoteRequestWriteDto(
    [property: StringLength(20)] string? Status,
    [property: JsonPropertyName("internal_notes")] string? InternalNotes,
    [property: JsonPropertyName("seller_response")] string? SellerResponse);

public sealed record HomeSectionItemWriteDto(
    [property: StringLength(40)] string? Section,
    int? Position,
    int? Product,
    [property: JsonPropertyName("product_id")] int? ProductId,
    [property: JsonPropertyName("is_active")] bool? IsActive);
