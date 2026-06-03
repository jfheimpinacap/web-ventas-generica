using JemNexus.Api.Models;
using Microsoft.AspNetCore.Identity;

namespace JemNexus.Api.Services;

public interface IPasswordHasherService
{
    string HashPassword(AppUser user, string password);
    bool VerifyPassword(AppUser user, string password);
}

public sealed class PasswordHasherService(IPasswordHasher<AppUser> passwordHasher) : IPasswordHasherService
{
    public string HashPassword(AppUser user, string password)
    {
        ArgumentNullException.ThrowIfNull(user);

        if (string.IsNullOrWhiteSpace(password))
        {
            throw new ArgumentException("Password is required.", nameof(password));
        }

        return passwordHasher.HashPassword(user, password);
    }

    public bool VerifyPassword(AppUser user, string password)
    {
        ArgumentNullException.ThrowIfNull(user);

        if (string.IsNullOrEmpty(password) || string.IsNullOrWhiteSpace(user.PasswordHash))
        {
            return false;
        }

        var result = passwordHasher.VerifyHashedPassword(user, user.PasswordHash, password);
        return result is PasswordVerificationResult.Success or PasswordVerificationResult.SuccessRehashNeeded;
    }
}
