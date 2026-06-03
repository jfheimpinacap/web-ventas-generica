using System.ComponentModel.DataAnnotations;

namespace JemNexus.Api.Options;

public sealed class JwtOptions
{
    public const string SectionName = "Jwt";

    [Required]
    public string Issuer { get; set; } = "JEM Nexus API";

    [Required]
    public string Audience { get; set; } = "JEM Nexus Frontend";

    public string Secret { get; set; } = string.Empty;

    [Range(1, 1440)]
    public int AccessTokenMinutes { get; set; } = 60;

    [Range(1, 90)]
    public int RefreshTokenDays { get; set; } = 7;
}
