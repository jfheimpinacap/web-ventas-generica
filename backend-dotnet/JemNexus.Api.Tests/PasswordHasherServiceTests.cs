using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Identity;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class PasswordHasherServiceTests
{
    [Fact]
    public void HashPasswordDoesNotReturnPlainText()
    {
        var service = CreateService();
        var user = new AppUser { Username = "demo" };

        var hash = service.HashPassword(user, "correct-password");

        Assert.NotEqual("correct-password", hash);
        Assert.NotEmpty(hash);
    }

    [Fact]
    public void VerifyPasswordAcceptsCorrectPassword()
    {
        var service = CreateService();
        var user = new AppUser { Username = "demo" };
        user.PasswordHash = service.HashPassword(user, "correct-password");

        Assert.True(service.VerifyPassword(user, "correct-password"));
    }

    [Fact]
    public void VerifyPasswordRejectsIncorrectPassword()
    {
        var service = CreateService();
        var user = new AppUser { Username = "demo" };
        user.PasswordHash = service.HashPassword(user, "correct-password");

        Assert.False(service.VerifyPassword(user, "wrong-password"));
    }

    private static PasswordHasherService CreateService()
    {
        return new PasswordHasherService(new PasswordHasher<AppUser>());
    }
}
