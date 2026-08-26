using Microsoft.AspNetCore.RateLimiting;
using System.ComponentModel.DataAnnotations;
using System.Security.Claims;
using System.Text.RegularExpressions;
using JemNexus.Api.Contracts.Admin;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static partial class AdminCustomerEndpoints
{
    private const int MaximumPageSize = 100;
    private const string DuplicateMessage = "Ya existe un cliente con ese RUT; si está inactivo, debe reactivarse.";

    public static IEndpointRouteBuilder MapAdminCustomerEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/admin/customers").RequireAuthorization("RequireSellerOrSupportAdmin").WithTags("Admin customers");
        group.MapGet("", SearchAsync);
        group.MapGet("/{id:int}", GetAsync);
        group.MapPost("", CreateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPut("/{id:int}", UpdateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPost("/{id:int}/deactivate", DeactivateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPost("/{id:int}/reactivate", ReactivateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        return endpoints;
    }

    private static async Task<IResult> SearchAsync(JemNexusDbContext db, CancellationToken ct, string? search, string status = "all", int page = 1, [FromQuery(Name = "page_size")] int pageSize = 20)
    {
        var errors = new Dictionary<string, string[]>();
        if (page < 1 || pageSize is < 1 or > MaximumPageSize) errors["pagination"] = [$"La página debe ser positiva y page_size debe estar entre 1 y {MaximumPageSize}."];
        status = status.Trim().ToLowerInvariant();
        if (status is not ("active" or "inactive" or "all")) errors["status"] = ["El estado debe ser active, inactive o all."];
        var term = CustomerTextNormalizer.Search(search);
        if (term.Length == 1 || term.Length > 200) errors["search"] = ["La búsqueda debe estar vacía o contener entre 2 y 200 caracteres."];
        if (errors.Count > 0) return Results.ValidationProblem(errors);
        var rutTerm = new string((search ?? string.Empty).Where(char.IsLetterOrDigit).ToArray()).ToUpperInvariant();
        var query = db.CustomerProfiles.AsNoTracking().AsQueryable();
        if (status == "active") query = query.Where(customer => customer.IsActive);
        if (status == "inactive") query = query.Where(customer => !customer.IsActive);
        if (term.Length > 0) query = query.Where(customer => customer.NormalizedBusinessName.Contains(term) || customer.NormalizedRut.Replace("-", "").Contains(rutTerm));
        var count = await query.CountAsync(ct);
        var values = await query.OrderBy(customer => customer.NormalizedBusinessName).ThenBy(customer => customer.Id).Skip((page - 1) * pageSize).Take(pageSize).ToListAsync(ct);
        return Results.Ok(new CustomerProfileSearchResponse(values.Select(CustomerProfileResponse.FromEntity).ToList(), page, pageSize, count));
    }

    private static async Task<IResult> GetAsync(int id, JemNexusDbContext db, CancellationToken ct)
    {
        var customer = await db.CustomerProfiles.AsNoTracking().FirstOrDefaultAsync(value => value.Id == id, ct);
        return id <= 0 || customer is null ? Results.NotFound() : Results.Ok(CustomerProfileResponse.FromEntity(customer));
    }

    private static async Task<IResult> CreateAsync(CustomerProfileCreateRequest request, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct)
    {
        var prepared = Prepare(request.BusinessName, request.Rut, request.BusinessActivity, request.Address, request.Phone, request.CityOrCommune, request.ContactName, request.Email);
        if (prepared.Errors.Count > 0) return Results.ValidationProblem(prepared.Errors);
        if (await db.CustomerProfiles.AnyAsync(value => value.NormalizedRut == prepared.Rut, ct)) return Results.Conflict(new { Detail = DuplicateMessage });
        var customer = new CustomerProfile();
        Apply(customer, prepared);
        customer.IsActive = true;
        customer.CreatedById = customer.UpdatedById = UserId(principal);
        db.CustomerProfiles.Add(customer);
        var conflict = await SaveAsync(db, ct);
        return conflict ?? Results.Created($"/api/admin/customers/{customer.Id}", CustomerProfileResponse.FromEntity(customer));
    }

    private static async Task<IResult> UpdateAsync(int id, CustomerProfileUpdateRequest request, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct)
    {
        var customer = await db.CustomerProfiles.FirstOrDefaultAsync(value => value.Id == id, ct);
        if (customer is null) return Results.NotFound();
        var prepared = Prepare(request.BusinessName, request.Rut, request.BusinessActivity, request.Address, request.Phone, request.CityOrCommune, request.ContactName, request.Email);
        if (prepared.Errors.Count > 0) return Results.ValidationProblem(prepared.Errors);
        if (await db.CustomerProfiles.AnyAsync(value => value.Id != id && value.NormalizedRut == prepared.Rut, ct)) return Results.Conflict(new { Detail = DuplicateMessage });
        Apply(customer, prepared);
        customer.UpdatedById = UserId(principal);
        var conflict = await SaveAsync(db, ct);
        return conflict ?? Results.Ok(CustomerProfileResponse.FromEntity(customer));
    }

    private static Task<IResult> DeactivateAsync(int id, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct) =>
        SetActiveAsync(id, false, principal, db, ct);

    private static Task<IResult> ReactivateAsync(int id, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct) =>
        SetActiveAsync(id, true, principal, db, ct);

    private static async Task<IResult> SetActiveAsync(int id, bool isActive, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct)
    {
        if (id <= 0) return Results.NotFound();
        var customer = await db.CustomerProfiles.FirstOrDefaultAsync(value => value.Id == id, ct);
        if (customer is null) return Results.NotFound();
        customer.IsActive = isActive;
        customer.UpdatedById = UserId(principal);
        db.Entry(customer).Property(value => value.IsActive).IsModified = true;
        await db.SaveChangesAsync(ct);
        return Results.Ok(CustomerProfileResponse.FromEntity(customer));
    }

    private static PreparedCustomer Prepare(string? businessName, string? rut, string? activity, string? address, string? phone, string? city, string? contact, string? email)
    {
        var value = new PreparedCustomer { BusinessName = CustomerTextNormalizer.Visible(businessName), Activity = CustomerTextNormalizer.Visible(activity), Address = CustomerTextNormalizer.Visible(address), Phone = CustomerTextNormalizer.Visible(phone), City = CustomerTextNormalizer.Visible(city), Contact = CustomerTextNormalizer.Visible(contact), Email = CustomerTextNormalizer.Optional(email) };
        ValidateRequired(value.Errors, "business_name", value.BusinessName, 2, 200);
        ValidateRequired(value.Errors, "business_activity", value.Activity, 2, 200);
        ValidateRequired(value.Errors, "address", value.Address, 3, 300);
        ValidateRequired(value.Errors, "phone", value.Phone, 5, 30);
        ValidateRequired(value.Errors, "city_or_commune", value.City, 2, 120);
        ValidateRequired(value.Errors, "contact_name", value.Contact, 2, 200);
        if (!ChileanRut.TryNormalize(rut, out var normalizedRut)) value.Errors["rut"] = [ChileanRut.InvalidMessage];
        value.Rut = normalizedRut;
        if (!string.IsNullOrEmpty(value.Email) && (value.Email.Length > 254 || !new EmailAddressAttribute().IsValid(value.Email))) value.Errors["email"] = ["El correo electrónico no tiene un formato válido o supera los 254 caracteres."];
        if (value.Phone.Length > 0 && (!PhoneRegex().IsMatch(value.Phone) || !value.Phone.Any(char.IsDigit))) value.Errors["phone"] = ["El teléfono contiene caracteres no permitidos."];
        return value;
    }

    private static void ValidateRequired(Dictionary<string, string[]> errors, string key, string value, int min, int max) { if (value.Length < min || value.Length > max) errors[key] = [$"El campo debe tener entre {min} y {max} caracteres."]; }
    private static void Apply(CustomerProfile target, PreparedCustomer value) { target.BusinessName = value.BusinessName; target.NormalizedBusinessName = CustomerTextNormalizer.Search(value.BusinessName); target.Rut = target.NormalizedRut = value.Rut; target.BusinessActivity = value.Activity; target.Address = value.Address; target.Phone = value.Phone; target.CityOrCommune = value.City; target.ContactName = value.Contact; target.Email = value.Email; }
    private static int? UserId(ClaimsPrincipal principal) => int.TryParse(principal.FindFirstValue(ClaimTypes.NameIdentifier) ?? principal.FindFirstValue("sub"), out var id) ? id : null;
    private static async Task<IResult?> SaveAsync(JemNexusDbContext db, CancellationToken ct) { try { await db.SaveChangesAsync(ct); return null; } catch (DbUpdateException exception) when (exception.InnerException is SqlException sql && sql.Number is 2601 or 2627 && sql.Message.Contains("IX_CustomerProfiles_NormalizedRut", StringComparison.Ordinal)) { return Results.Conflict(new { Detail = DuplicateMessage }); } }
    [GeneratedRegex(@"^[0-9+() .-]+$", RegexOptions.CultureInvariant)] private static partial Regex PhoneRegex();
    private sealed class PreparedCustomer
    {
        public string BusinessName { get; init; } = string.Empty;
        public string Rut { get; set; } = string.Empty;
        public string Activity { get; init; } = string.Empty;
        public string Address { get; init; } = string.Empty;
        public string Phone { get; init; } = string.Empty;
        public string City { get; init; } = string.Empty;
        public string Contact { get; init; } = string.Empty;
        public string? Email { get; init; }
        public Dictionary<string, string[]> Errors { get; } = [];
    }
}
