using JemNexus.Api.Models;

namespace JemNexus.Api.Contracts.Admin;

public sealed record AdminUserCreateRequest(
    string? Username,
    string? Email,
    string? FullName,
    string? Password,
    bool IsActive = true);

public sealed record AdminUserUpdateRequest(
    string? Username,
    string? Email,
    string? FullName,
    bool? IsActive,
    string? Password);

public sealed record AdminUserResponse(
    int Id,
    string Username,
    string? Email,
    string? FullName,
    string Role,
    bool IsActive,
    bool IsStaff,
    bool IsSuperuser,
    DateTimeOffset? LastLoginAt,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt)
{
    public static AdminUserResponse FromUser(AppUser user) => new(
        user.Id,
        user.Username,
        user.Email,
        user.FullName,
        user.Role,
        user.IsActive,
        user.IsStaff,
        user.IsSuperuser,
        user.LastLoginAt,
        user.CreatedAt,
        user.UpdatedAt);
}
