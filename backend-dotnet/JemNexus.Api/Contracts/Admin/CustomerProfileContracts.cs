using JemNexus.Api.Models;

namespace JemNexus.Api.Contracts.Admin;

public sealed record CustomerProfileCreateRequest(string? BusinessName, string? Rut, string? BusinessActivity, string? Address, string? Phone, string? CityOrCommune, string? ContactName, string? Email);
public sealed record CustomerProfileUpdateRequest(string? BusinessName, string? Rut, string? BusinessActivity, string? Address, string? Phone, string? CityOrCommune, string? ContactName, string? Email);
public sealed record CustomerProfileResponse(int Id, string BusinessName, string Rut, string BusinessActivity, string Address, string Phone, string CityOrCommune, string ContactName, string? Email, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt)
{
    public static CustomerProfileResponse FromEntity(CustomerProfile value) => new(value.Id, value.BusinessName, value.Rut, value.BusinessActivity, value.Address, value.Phone, value.CityOrCommune, value.ContactName, value.Email, value.CreatedAt, value.UpdatedAt);
}
public sealed record CustomerProfileSearchResponse(IReadOnlyList<CustomerProfileResponse> Results, int Page, int PageSize, int Count);
