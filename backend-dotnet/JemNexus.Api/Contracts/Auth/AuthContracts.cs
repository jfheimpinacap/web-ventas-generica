using System.Text.Json.Serialization;
using JemNexus.Api.Models;

namespace JemNexus.Api.Contracts.Auth;

public sealed record LoginRequest(string Username, string Password);

public sealed record RefreshRequest(string Refresh);

public sealed record AuthUserResponse(
    int Id,
    string Username,
    string? Email,
    string Role,
    [property: JsonPropertyName("is_staff")] bool IsStaff,
    [property: JsonPropertyName("is_superuser")] bool IsSuperuser)
{
    public static AuthUserResponse FromUser(AppUser user)
    {
        return new AuthUserResponse(user.Id, user.Username, user.Email, user.Role, user.IsStaff, user.IsSuperuser);
    }
}

public sealed record LoginResponse(string Access, string Refresh, AuthUserResponse User);

public sealed record RefreshResponse(string Access);
