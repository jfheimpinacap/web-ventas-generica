using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace JemNexus.Api.Services;

public sealed record TokenPair(string Access, string Refresh, DateTimeOffset AccessExpiresAt, DateTimeOffset RefreshExpiresAt);

public interface IJwtTokenService
{
    string GenerateAccessToken(AppUser user);
    TokenPair GenerateTokenPair(AppUser user);
    string GenerateRefreshToken();
    string HashRefreshToken(string refreshToken);
}

public sealed class JwtTokenService(IOptions<JwtOptions> jwtOptions) : IJwtTokenService
{
    private readonly JwtOptions _options = jwtOptions.Value;

    public string GenerateAccessToken(AppUser user)
    {
        ArgumentNullException.ThrowIfNull(user);

        var now = DateTimeOffset.UtcNow;
        var expires = now.AddMinutes(_options.AccessTokenMinutes);
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(GetRequiredSecret()));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new(JwtRegisteredClaimNames.UniqueName, user.Username),
            new(ClaimTypes.Name, user.Username),
            new(ClaimTypes.Role, user.Role),
            new("role", user.Role),
            new("is_staff", user.IsStaff.ToString().ToLowerInvariant()),
            new("is_superuser", user.IsSuperuser.ToString().ToLowerInvariant())
        };

        if (!string.IsNullOrWhiteSpace(user.Email))
        {
            claims.Add(new Claim(JwtRegisteredClaimNames.Email, user.Email));
            claims.Add(new Claim(ClaimTypes.Email, user.Email));
        }

        var token = new JwtSecurityToken(
            issuer: _options.Issuer,
            audience: _options.Audience,
            claims: claims,
            notBefore: now.UtcDateTime,
            expires: expires.UtcDateTime,
            signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    public TokenPair GenerateTokenPair(AppUser user)
    {
        var now = DateTimeOffset.UtcNow;
        return new TokenPair(
            GenerateAccessToken(user),
            GenerateRefreshToken(),
            now.AddMinutes(_options.AccessTokenMinutes),
            now.AddDays(_options.RefreshTokenDays));
    }

    public string GenerateRefreshToken()
    {
        Span<byte> bytes = stackalloc byte[64];
        RandomNumberGenerator.Fill(bytes);
        return Base64UrlEncoder.Encode(bytes.ToArray());
    }

    public string HashRefreshToken(string refreshToken)
    {
        if (string.IsNullOrWhiteSpace(refreshToken))
        {
            throw new ArgumentException("Refresh token is required.", nameof(refreshToken));
        }

        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(refreshToken));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private string GetRequiredSecret()
    {
        if (string.IsNullOrWhiteSpace(_options.Secret))
        {
            throw new InvalidOperationException("JWT secret is required. Configure Jwt:Secret or JWT_SECRET outside the repository.");
        }

        return _options.Secret;
    }
}
