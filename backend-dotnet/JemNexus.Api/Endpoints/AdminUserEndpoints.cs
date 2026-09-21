using System.ComponentModel.DataAnnotations;
using System.Data;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using JemNexus.Api.Contracts.Admin;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static partial class AdminUserEndpoints
{
    private const string Policy = "RequireSupportAdmin";
    private static readonly string[] ManagedRoles = [AppRoles.Seller, AppRoles.SupportAdmin];

    public static IEndpointRouteBuilder MapAdminUserEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/admin/users").RequireAuthorization(Policy).WithTags("Admin users");
        group.MapGet("", ListAsync);
        group.MapGet("/permission-catalog", Catalog);
        group.MapGet("/{id:int}", GetAsync);
        group.MapPost("", CreateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPut("/{id:int}", UpdateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapPatch("/{id:int}", UpdateAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        group.MapDelete("/{id:int}", DeleteAsync).RequireRateLimiting(RateLimitPolicies.AuthenticatedWrite);
        return endpoints;
    }

    private static IResult Catalog() => Results.Ok(new UserPermissionCatalogResponse(
        ManagedRoles.Order(StringComparer.Ordinal).ToArray(),
        AppPermissions.SellerGrantable.Order(StringComparer.Ordinal).ToArray(),
        AppPermissions.Reserved.Order(StringComparer.Ordinal).ToArray()));

    private static async Task<IResult> ListAsync(string? search, [FromQuery(Name = "is_active")] bool? isActive,
        string? role, JemNexusDbContext db, CancellationToken ct)
    {
        if (role is not null && !ManagedRoles.Contains(role, StringComparer.Ordinal))
            return Validation("role", "El rol indicado no es válido.");
        var query = db.AppUsers.AsNoTracking().Include(user => user.Permissions)
            .Where(user => user.Role == AppRoles.Seller || user.Role == AppRoles.SupportAdmin);
        var term = search?.Trim().ToLower();
        if (!string.IsNullOrEmpty(term)) query = query.Where(user => user.Username.ToLower().Contains(term)
            || (user.Email != null && user.Email.ToLower().Contains(term))
            || (user.FullName != null && user.FullName.ToLower().Contains(term))
            || (user.SellerCode != null && user.SellerCode.ToLower().Contains(term)));
        if (isActive.HasValue) query = query.Where(user => user.IsActive == isActive.Value);
        if (role is not null) query = query.Where(user => user.Role == role);
        var users = await query.OrderBy(user => user.Role).ThenBy(user => user.Username).ThenBy(user => user.Id).ToListAsync(ct);
        return Results.Ok(users.Select(Response));
    }

    private static async Task<IResult> GetAsync(int id, JemNexusDbContext db, CancellationToken ct)
    {
        var user = await FindManagedAsync(id, db, ct);
        return user is null ? Results.NotFound() : Results.Ok(Response(user));
    }

    private static async Task<IResult> CreateAsync(AdminUserCreateRequest request, JemNexusDbContext db,
        IPasswordHasherService hasher, ISellerCodeGenerator sellerCodeGenerator, CancellationToken ct)
    {
        var role = request.Role ?? AppRoles.Seller;
        var username = request.Username?.Trim() ?? string.Empty;
        var email = NormalizeOptional(request.Email); var fullName = NormalizeOptional(request.FullName); var phone = NormalizeOptional(request.Phone);
        var errors = Validate(username, email, fullName, phone, request.Password, true);
        ValidateRoleAndPermissions(errors, role, request.Permissions);
        await AddUniquenessErrorsAsync(errors, username, email, null, db, ct);
        if (errors.Count > 0) return Results.ValidationProblem(errors);

        var user = new AppUser { Username = username, Email = email, FullName = fullName, Phone = phone,
            IsActive = request.IsActive, Role = role, IsStaff = true, IsSuperuser = role == AppRoles.SupportAdmin,
            SellerCode = role == AppRoles.Seller ? await sellerCodeGenerator.GenerateAsync(ct) : null };
        user.PasswordHash = hasher.HashPassword(user, request.Password!);
        if (role == AppRoles.Seller) SetPermissions(user, request.Permissions ?? AppPermissions.SellerGrantable);
        db.AppUsers.Add(user);
        var failure = await SaveWithUniqueConflictAsync(db, ct);
        return failure ?? Results.Created($"/api/admin/users/{user.Id}", Response(user));
    }

    private static async Task<IResult> UpdateAsync(int id, AdminUserUpdateRequest request, ClaimsPrincipal principal,
        JemNexusDbContext db, IPasswordHasherService hasher, ISellerCodeGenerator sellerCodeGenerator, CancellationToken ct)
    {
        await using var transaction = db.Database.IsRelational()
            ? await db.Database.BeginTransactionAsync(IsolationLevel.Serializable, ct) : null;
        var user = await FindManagedAsync(id, db, ct);
        if (user is null) return Results.NotFound();
        var oldRole = user.Role; var role = request.Role ?? oldRole;
        var username = request.Username?.Trim() ?? user.Username;
        var email = NormalizeOptional(request.Email); var fullName = NormalizeOptional(request.FullName); var phone = NormalizeOptional(request.Phone);
        var password = string.IsNullOrWhiteSpace(request.Password) ? null : request.Password;
        var reactivating = !user.IsActive && request.IsActive == true;
        var errors = Validate(username, email, fullName, phone, password, reactivating);
        ValidateRoleAndPermissions(errors, role, request.Permissions);
        await AddUniquenessErrorsAsync(errors, username, email, id, db, ct);
        if (errors.Count > 0) return Results.ValidationProblem(errors);

        var currentId = UserId(principal);
        if (id == currentId && request.IsActive == false)
            return Results.Conflict(new { Detail = "No puedes desactivar tu sesión actual." });
        if (id == currentId && oldRole == AppRoles.SupportAdmin && role != AppRoles.SupportAdmin)
            return Results.Conflict(new { Detail = "No puedes cambiar el rol de tu sesión actual." });
        var deactivatingAdmin = oldRole == AppRoles.SupportAdmin && user.IsActive
            && ((request.IsActive == false) || role != AppRoles.SupportAdmin);
        if (deactivatingAdmin && await ActiveAdminCountAsync(db, ct) <= 1)
            return Results.Conflict(new { Detail = "Debe existir al menos otro superadministrador activo." });

        var activeChanged = request.IsActive.HasValue && request.IsActive.Value != user.IsActive;
        var roleChanged = role != oldRole;
        user.Username = username; user.Email = email; user.FullName = fullName; user.Phone = phone;
        user.IsActive = request.IsActive ?? user.IsActive; user.Role = role; user.IsStaff = true;
        user.IsSuperuser = role == AppRoles.SupportAdmin;
        var permissionsChanged = false;
        if (role == AppRoles.SupportAdmin) { user.SellerCode = null; permissionsChanged = user.Permissions.Count > 0; user.Permissions.Clear(); }
        else
        {
            if (oldRole == AppRoles.SupportAdmin) user.SellerCode = await sellerCodeGenerator.GenerateAsync(ct);
            var desired = request.Permissions ?? (oldRole == AppRoles.SupportAdmin ? AppPermissions.SellerGrantable : null);
            if (desired is not null) { permissionsChanged = !SamePermissions(user, desired); SetPermissions(user, desired); }
        }
        if (password is not null) user.PasswordHash = hasher.HashPassword(user, password);
        if (password is not null || roleChanged || permissionsChanged || activeChanged) await RevokeRefreshTokensAsync(user.Id, db, ct);
        var failure = await SaveWithUniqueConflictAsync(db, ct);
        if (failure is not null) return failure;
        if (transaction is not null) await transaction.CommitAsync(ct);
        return Results.Ok(Response(user));
    }

    private static async Task<IResult> DeleteAsync(int id, ClaimsPrincipal principal, JemNexusDbContext db,
        IPasswordHasherService hasher, CancellationToken ct)
    {
        await using var transaction = db.Database.IsRelational()
            ? await db.Database.BeginTransactionAsync(IsolationLevel.Serializable, ct) : null;
        var user = await FindManagedAsync(id, db, ct);
        if (user is null) return Results.NotFound();
        if (id == UserId(principal)) return Results.Conflict(new { Detail = "No puedes desactivar tu sesión actual." });
        if (!user.IsActive) { if (transaction is not null) await transaction.CommitAsync(ct); return Results.NoContent(); }
        if (user.Role == AppRoles.SupportAdmin && await ActiveAdminCountAsync(db, ct) <= 1)
            return Results.Conflict(new { Detail = "Debe existir al menos otro superadministrador activo." });
        user.IsActive = false;
        user.PasswordHash = hasher.HashPassword(user, Convert.ToHexString(RandomNumberGenerator.GetBytes(64)));
        await RevokeRefreshTokensAsync(user.Id, db, ct); await db.SaveChangesAsync(ct);
        if (transaction is not null) await transaction.CommitAsync(ct);
        return Results.NoContent();
    }

    private static AdminUserResponse Response(AppUser user) => AdminUserResponse.FromUser(user,
        user.Role == AppRoles.SupportAdmin ? AppPermissions.All.Order(StringComparer.Ordinal).ToArray()
        : user.Permissions.Select(value => value.Permission).Where(AppPermissions.IsSellerGrantable).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray());
    private static Task<AppUser?> FindManagedAsync(int id, JemNexusDbContext db, CancellationToken ct) => db.AppUsers.Include(user => user.Permissions)
        .FirstOrDefaultAsync(user => user.Id == id && (user.Role == AppRoles.Seller || user.Role == AppRoles.SupportAdmin), ct);
    private static Task<int> ActiveAdminCountAsync(JemNexusDbContext db, CancellationToken ct) => db.AppUsers.CountAsync(user => user.Role == AppRoles.SupportAdmin && user.IsActive, ct);
    private static int UserId(ClaimsPrincipal principal) => int.TryParse(principal.FindFirstValue(ClaimTypes.NameIdentifier) ?? principal.FindFirstValue("sub"), out var id) ? id : 0;
    private static bool SamePermissions(AppUser user, IReadOnlyList<string> desired) => user.Permissions.Select(value => value.Permission).ToHashSet(StringComparer.Ordinal).SetEquals(desired);
    private static void SetPermissions(AppUser user, IEnumerable<string> permissions) { user.Permissions.Clear(); foreach (var permission in permissions.Order(StringComparer.Ordinal)) user.Permissions.Add(new AppUserPermission { User = user, Permission = permission }); }

    private static void ValidateRoleAndPermissions(Dictionary<string, string[]> errors, string role, IReadOnlyList<string>? permissions)
    {
        if (!ManagedRoles.Contains(role, StringComparer.Ordinal)) errors["role"] = ["El rol indicado no es válido."];
        if (permissions is null) return;
        if (permissions.Count != permissions.Distinct(StringComparer.Ordinal).Count()) errors["permissions"] = ["No se permiten permisos duplicados."];
        else if (permissions.Any(permission => !AppPermissions.IsKnown(permission))) errors["permissions"] = ["La lista contiene un permiso desconocido o con formato inválido."];
        else if (role == AppRoles.Seller && permissions.Any(permission => !AppPermissions.IsSellerGrantable(permission))) errors["permissions"] = ["Un vendedor no puede recibir permisos reservados."];
        else if (role == AppRoles.SupportAdmin && permissions.Count > 0) errors["permissions"] = ["Los permisos del superadministrador se derivan de su rol."];
    }
    private static async Task RevokeRefreshTokensAsync(int userId, JemNexusDbContext db, CancellationToken ct) { var now = DateTimeOffset.UtcNow; foreach (var token in await db.AppRefreshTokens.Where(token => token.UserId == userId && token.RevokedAt == null).ToListAsync(ct)) token.RevokedAt = now; }
    private static Dictionary<string, string[]> Validate(string username, string? email, string? fullName, string? phone, string? password, bool passwordRequired)
    {
        var errors = new Dictionary<string, string[]>();
        if (string.IsNullOrWhiteSpace(username)) errors["username"] = ["El nombre de usuario es obligatorio."];
        else if (username.Length is < 3 or > 150 || !UsernameRegex().IsMatch(username)) errors["username"] = ["El nombre de usuario debe tener entre 3 y 150 caracteres y solo puede contener letras, números, punto, guion y guion bajo."];
        if (email is { Length: > 254 } || (email is not null && !new EmailAddressAttribute().IsValid(email))) errors["email"] = ["El correo electrónico no tiene un formato válido o supera los 254 caracteres."];
        if (fullName is { Length: > 180 }) errors["full_name"] = ["El nombre completo no puede superar los 180 caracteres."];
        if (phone is { Length: > 32 }) errors["phone"] = ["El teléfono no puede superar los 32 caracteres."];
        if (passwordRequired && string.IsNullOrEmpty(password)) errors["password"] = ["La contraseña es obligatoria."];
        else if (!string.IsNullOrEmpty(password) && !IsStrongPassword(password)) errors["password"] = ["La contraseña debe tener entre 12 y 128 caracteres e incluir mayúscula, minúscula, número y símbolo."];
        return errors;
    }
    private static bool IsStrongPassword(string password) => password.Length is >= 12 and <= 128 && password.Any(char.IsUpper) && password.Any(char.IsLower) && password.Any(char.IsDigit) && password.Any(character => !char.IsLetterOrDigit(character));
    private static async Task AddUniquenessErrorsAsync(Dictionary<string, string[]> errors, string username, string? email, int? excludedId, JemNexusDbContext db, CancellationToken ct)
    { var normalizedUsername = username.ToLower(); if (await db.AppUsers.AnyAsync(user => user.Id != excludedId && user.Username.ToLower() == normalizedUsername, ct)) errors["username"] = ["El nombre de usuario ya está en uso."]; if (email is not null) { var normalizedEmail = email.ToLower(); if (await db.AppUsers.AnyAsync(user => user.Id != excludedId && user.Email != null && user.Email.ToLower() == normalizedEmail, ct)) errors["email"] = ["El correo electrónico ya está en uso."]; } }
    private static async Task<IResult?> SaveWithUniqueConflictAsync(JemNexusDbContext db, CancellationToken ct) { try { await db.SaveChangesAsync(ct); return null; } catch (DbUpdateException) { return Results.Conflict(new { Detail = "El nombre de usuario o el correo electrónico ya está en uso." }); } }
    private static IResult Validation(string key, string message) => Results.ValidationProblem(new Dictionary<string, string[]> { [key] = [message] });
    private static string? NormalizeOptional(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    [GeneratedRegex(@"^[\p{L}\p{N}._-]+$", RegexOptions.CultureInvariant)] private static partial Regex UsernameRegex();
}
