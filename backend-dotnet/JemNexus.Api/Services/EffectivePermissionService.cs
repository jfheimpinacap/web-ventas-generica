using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Services;

public interface IEffectivePermissionService
{
    Task<IReadOnlyList<string>> GetAsync(AppUser user, CancellationToken cancellationToken = default);
}

public sealed class EffectivePermissionService(JemNexusDbContext db) : IEffectivePermissionService
{
    public async Task<IReadOnlyList<string>> GetAsync(AppUser user, CancellationToken cancellationToken = default)
    {
        if (!user.IsActive) return [];
        if (string.Equals(user.Role, AppRoles.SupportAdmin, StringComparison.Ordinal)) return AppPermissions.All;
        if (!string.Equals(user.Role, AppRoles.Seller, StringComparison.Ordinal)) return [];

        var persisted = await db.AppUserPermissions.AsNoTracking()
            .Where(value => value.UserId == user.Id)
            .Select(value => value.Permission)
            .ToListAsync(cancellationToken);
        return persisted.Where(AppPermissions.IsSellerGrantable)
            .Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
    }
}

public static class DefaultSellerPermissions
{
    public static void EnsureAssigned(AppUser user)
    {
        if (!string.Equals(user.Role, AppRoles.Seller, StringComparison.Ordinal)) return;
        var existing = user.Permissions.Select(value => value.Permission).ToHashSet(StringComparer.Ordinal);
        foreach (var permission in AppPermissions.SellerGrantable)
            if (existing.Add(permission)) user.Permissions.Add(new AppUserPermission { User = user, Permission = permission });
    }
}
