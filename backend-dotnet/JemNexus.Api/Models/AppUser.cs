namespace JemNexus.Api.Models;

public sealed class AppUser
{
    public int Id { get; set; }
    public string Username { get; set; } = string.Empty;
    public string? Email { get; set; }
    public string PasswordHash { get; set; } = string.Empty;
    public string Role { get; set; } = AppRoles.Seller;
    public string? FullName { get; set; }
    public bool IsActive { get; set; } = true;
    public bool IsStaff { get; set; }
    public bool IsSuperuser { get; set; }
    public DateTimeOffset? LastLoginAt { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }

    public ICollection<AppRefreshToken> RefreshTokens { get; set; } = new List<AppRefreshToken>();
}
