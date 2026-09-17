using System.Security.Claims;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Authorization;

public sealed record PermissionRequirement(string Permission) : IAuthorizationRequirement;

public sealed class PermissionAuthorizationHandler(JemNexusDbContext db) : AuthorizationHandler<PermissionRequirement>
{
    protected override async Task HandleRequirementAsync(AuthorizationHandlerContext context, PermissionRequirement requirement)
    {
        if (!AppPermissions.IsKnown(requirement.Permission)) return;
        var idValue = context.User.FindFirstValue(ClaimTypes.NameIdentifier) ?? context.User.FindFirstValue("sub");
        if (!int.TryParse(idValue, out var userId)) return;

        var user = await db.AppUsers.AsNoTracking()
            .Where(candidate => candidate.Id == userId && candidate.IsActive)
            .Select(candidate => new { candidate.Role })
            .SingleOrDefaultAsync();
        if (user is null) return;
        if (string.Equals(user.Role, AppRoles.SupportAdmin, StringComparison.Ordinal))
        {
            context.Succeed(requirement);
            return;
        }

        if (!string.Equals(user.Role, AppRoles.Seller, StringComparison.Ordinal)
            || !AppPermissions.IsSellerGrantable(requirement.Permission)) return;

        if (await db.AppUserPermissions.AsNoTracking().AnyAsync(value =>
                value.UserId == userId && value.Permission == requirement.Permission))
            context.Succeed(requirement);
    }
}

public static class PermissionAuthorizationExtensions
{
    public static TBuilder RequirePermission<TBuilder>(this TBuilder builder, string permission)
        where TBuilder : IEndpointConventionBuilder
    {
        ArgumentException.ThrowIfNullOrEmpty(permission);
        return builder.RequireAuthorization(policy => policy.AddRequirements(new PermissionRequirement(permission)));
    }
}
