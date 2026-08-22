using Microsoft.AspNetCore.RateLimiting;
using System.ComponentModel.DataAnnotations;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using JemNexus.Api.Contracts.Admin;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static partial class AdminUserEndpoints
{
    private const string Policy = "RequireSupportAdmin";

    public static IEndpointRouteBuilder MapAdminUserEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/admin/users").RequireAuthorization(Policy).WithTags("Admin users");
        group.MapGet("", ListAsync);
        group.MapGet("/{id:int}", GetAsync);
        group.MapPost("", CreateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPut("/{id:int}", UpdateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPatch("/{id:int}", UpdateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapDelete("/{id:int}", DeleteAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        return endpoints;
    }

    private static async Task<IResult> ListAsync(string? search, [FromQuery(Name = "is_active")] bool? isActive, JemNexusDbContext db, CancellationToken ct)
    {
        var query = db.AppUsers.AsNoTracking().Where(user => user.Role == AppRoles.Seller);
        var term = search?.Trim().ToLower();
        if (!string.IsNullOrEmpty(term))
        {
            query = query.Where(user => user.Username.ToLower().Contains(term)
                || (user.Email != null && user.Email.ToLower().Contains(term))
                || (user.FullName != null && user.FullName.ToLower().Contains(term))
                || (user.SellerCode != null && user.SellerCode.ToLower().Contains(term)));
        }

        if (isActive.HasValue)
        {
            query = query.Where(user => user.IsActive == isActive.Value);
        }

        var users = await query.OrderBy(user => user.SellerCode).ThenBy(user => user.Username).ThenBy(user => user.Id).ToListAsync(ct);
        return Results.Ok(users.Select(AdminUserResponse.FromUser));
    }

    private static async Task<IResult> GetAsync(int id, JemNexusDbContext db, CancellationToken ct)
    {
        var user = await FindSellerAsync(id, db, ct);
        return user is null ? Results.NotFound() : Results.Ok(AdminUserResponse.FromUser(user));
    }

    private static async Task<IResult> CreateAsync(
        AdminUserCreateRequest request,
        JemNexusDbContext db,
        IPasswordHasherService hasher,
        ISellerCodeGenerator sellerCodeGenerator,
        CancellationToken ct)
    {
        var username = request.Username?.Trim() ?? string.Empty;
        var email = NormalizeOptional(request.Email);
        var fullName = NormalizeOptional(request.FullName);
        var errors = Validate(username, email, fullName, request.Password, passwordRequired: true);
        await AddUniquenessErrorsAsync(errors, username, email, null, db, ct);
        if (errors.Count > 0)
        {
            return Results.ValidationProblem(errors);
        }

        var user = new AppUser
        {
            Username = username,
            SellerCode = await sellerCodeGenerator.GenerateAsync(ct),
            Email = email,
            FullName = fullName,
            IsActive = request.IsActive,
            Role = AppRoles.Seller,
            IsStaff = true,
            IsSuperuser = false
        };
        user.PasswordHash = hasher.HashPassword(user, request.Password!);
        db.AppUsers.Add(user);

        var failure = await SaveWithUniqueConflictAsync(db, ct);
        return failure ?? Results.Created($"/api/admin/users/{user.Id}", AdminUserResponse.FromUser(user));
    }

    private static async Task<IResult> UpdateAsync(
        int id,
        AdminUserUpdateRequest request,
        JemNexusDbContext db,
        IPasswordHasherService hasher,
        CancellationToken ct)
    {
        var user = await FindSellerAsync(id, db, ct);
        if (user is null)
        {
            return Results.NotFound();
        }

        var username = request.Username?.Trim() ?? user.Username;
        var email = NormalizeOptional(request.Email);
        var fullName = NormalizeOptional(request.FullName);
        var password = string.IsNullOrWhiteSpace(request.Password) ? null : request.Password;
        var reactivating = !user.IsActive && request.IsActive == true;
        var errors = Validate(username, email, fullName, password, passwordRequired: reactivating);
        await AddUniquenessErrorsAsync(errors, username, email, id, db, ct);
        if (errors.Count > 0)
        {
            return Results.ValidationProblem(errors);
        }

        user.Username = username;
        user.Email = email;
        user.FullName = fullName;
        user.IsActive = request.IsActive ?? user.IsActive;
        user.Role = AppRoles.Seller;
        user.IsStaff = true;
        user.IsSuperuser = false;

        if (password is not null)
        {
            user.PasswordHash = hasher.HashPassword(user, password);
            await RevokeRefreshTokensAsync(user.Id, db, ct);
        }

        var failure = await SaveWithUniqueConflictAsync(db, ct);
        return failure ?? Results.Ok(AdminUserResponse.FromUser(user));
    }

    private static async Task<IResult> DeleteAsync(
        int id,
        JemNexusDbContext db,
        IPasswordHasherService hasher,
        CancellationToken ct)
    {
        var user = await FindSellerAsync(id, db, ct);
        if (user is null)
        {
            return Results.NotFound();
        }

        user.IsActive = false;
        user.Role = AppRoles.Seller;
        user.IsStaff = true;
        user.IsSuperuser = false;
        user.PasswordHash = hasher.HashPassword(user, Convert.ToHexString(RandomNumberGenerator.GetBytes(64)));
        await RevokeRefreshTokensAsync(user.Id, db, ct);
        await db.SaveChangesAsync(ct);
        return Results.NoContent();
    }

    private static Task<AppUser?> FindSellerAsync(int id, JemNexusDbContext db, CancellationToken ct) =>
        db.AppUsers.FirstOrDefaultAsync(user => user.Id == id && user.Role == AppRoles.Seller, ct);

    private static async Task RevokeRefreshTokensAsync(int userId, JemNexusDbContext db, CancellationToken ct)
    {
        var now = DateTimeOffset.UtcNow;
        var activeTokens = await db.AppRefreshTokens
            .Where(token => token.UserId == userId && token.RevokedAt == null)
            .ToListAsync(ct);
        foreach (var token in activeTokens)
        {
            token.RevokedAt = now;
        }
    }

    private static Dictionary<string, string[]> Validate(
        string username,
        string? email,
        string? fullName,
        string? password,
        bool passwordRequired)
    {
        var errors = new Dictionary<string, string[]>();
        if (string.IsNullOrWhiteSpace(username))
            errors["username"] = ["El nombre de usuario es obligatorio."];
        else if (username.Length is < 3 or > 150 || !UsernameRegex().IsMatch(username))
            errors["username"] = ["El nombre de usuario debe tener entre 3 y 150 caracteres y solo puede contener letras, números, punto, guion y guion bajo."];

        if (email is { Length: > 254 } || (email is not null && !new EmailAddressAttribute().IsValid(email)))
            errors["email"] = ["El correo electrónico no tiene un formato válido o supera los 254 caracteres."];
        if (fullName is { Length: > 180 })
            errors["full_name"] = ["El nombre completo no puede superar los 180 caracteres."];

        if (passwordRequired && string.IsNullOrEmpty(password))
            errors["password"] = ["La contraseña es obligatoria."];
        else if (!string.IsNullOrEmpty(password) && !IsStrongPassword(password))
            errors["password"] = ["La contraseña debe tener entre 12 y 128 caracteres e incluir mayúscula, minúscula, número y símbolo."];
        return errors;
    }

    private static bool IsStrongPassword(string password) =>
        password.Length is >= 12 and <= 128
        && password.Any(char.IsUpper)
        && password.Any(char.IsLower)
        && password.Any(char.IsDigit)
        && password.Any(character => !char.IsLetterOrDigit(character));

    private static async Task AddUniquenessErrorsAsync(
        Dictionary<string, string[]> errors,
        string username,
        string? email,
        int? excludedId,
        JemNexusDbContext db,
        CancellationToken ct)
    {
        var normalizedUsername = username.ToLower();
        if (await db.AppUsers.AnyAsync(user => user.Id != excludedId && user.Username.ToLower() == normalizedUsername, ct))
            errors["username"] = ["El nombre de usuario ya está en uso."];
        if (email is not null)
        {
            var normalizedEmail = email.ToLower();
            if (await db.AppUsers.AnyAsync(user => user.Id != excludedId && user.Email != null && user.Email.ToLower() == normalizedEmail, ct))
                errors["email"] = ["El correo electrónico ya está en uso."];
        }
    }

    private static async Task<IResult?> SaveWithUniqueConflictAsync(JemNexusDbContext db, CancellationToken ct)
    {
        try
        {
            await db.SaveChangesAsync(ct);
            return null;
        }
        catch (DbUpdateException)
        {
            return Results.Conflict(new { Detail = "El nombre de usuario o el correo electrónico ya está en uso." });
        }
    }

    private static string? NormalizeOptional(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    [GeneratedRegex(@"^[\p{L}\p{N}._-]+$", RegexOptions.CultureInvariant)]
    private static partial Regex UsernameRegex();
}
