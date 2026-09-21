using JemNexus.Api.Models;

namespace JemNexus.Api.Contracts.Admin;

public sealed record AdminUserCreateRequest(
    string? Username, string? Email, string? FullName, string? Phone, string? Password,
    bool IsActive = true, string? Role = null, IReadOnlyList<string>? Permissions = null);

public sealed record AdminUserUpdateRequest(
    string? Username, string? Email, string? FullName, string? Phone, bool? IsActive,
    string? Password, string? Role = null, IReadOnlyList<string>? Permissions = null);

public sealed record UserPermissionCatalogResponse(
    IReadOnlyList<string> Roles,
    IReadOnlyList<string> SellerGrantable,
    IReadOnlyList<string> Reserved);

public sealed record AdminUserResponse(
    int Id, string Username, string? SellerCode, string? Email, string? FullName, string? Phone,
    string Role, bool IsActive, bool IsStaff, bool IsSuperuser, IReadOnlyList<string> Permissions,
    DateTimeOffset? LastLoginAt, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt)
{
    public static AdminUserResponse FromUser(AppUser user, IReadOnlyList<string> permissions) => new(
        user.Id, user.Username, user.SellerCode, user.Email, user.FullName, user.Phone, user.Role,
        user.IsActive, user.IsStaff, user.IsSuperuser, permissions, user.LastLoginAt, user.CreatedAt, user.UpdatedAt);
}
