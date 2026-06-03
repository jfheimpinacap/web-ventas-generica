using System.IdentityModel.Tokens.Jwt;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.Extensions.Options;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class JwtTokenServiceTests
{
    [Fact]
    public void GenerateAccessTokenIncludesUserClaimsAndExpiration()
    {
        var service = CreateService();
        var user = new AppUser
        {
            Id = 7,
            Username = "demo",
            Email = "demo@example.test",
            Role = AppRoles.Seller,
            IsStaff = true,
            IsSuperuser = false
        };

        var token = service.GenerateAccessToken(user);
        var jwt = new JwtSecurityTokenHandler().ReadJwtToken(token);

        Assert.False(string.IsNullOrWhiteSpace(token));
        Assert.Contains(jwt.Claims, claim => claim.Type == JwtRegisteredClaimNames.Sub && claim.Value == "7");
        Assert.Contains(jwt.Claims, claim => claim.Type == JwtRegisteredClaimNames.UniqueName && claim.Value == "demo");
        Assert.Contains(jwt.Claims, claim => claim.Type == "role" && claim.Value == AppRoles.Seller);
        Assert.True(jwt.ValidTo > DateTime.UtcNow);
    }

    private static JwtTokenService CreateService()
    {
        return new JwtTokenService(Options.Create(new JwtOptions
        {
            Issuer = "JEM Nexus API",
            Audience = "JEM Nexus Frontend",
            Secret = "unit-test-jwt-secret-not-for-production-32chars",
            AccessTokenMinutes = 60,
            RefreshTokenDays = 7
        }));
    }
}
