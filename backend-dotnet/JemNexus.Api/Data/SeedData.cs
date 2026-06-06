using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace JemNexus.Api.Data;

public static class SeedData
{
    public static async Task SeedUsersAsync(
        IServiceProvider services,
        IHostEnvironment environment,
        CancellationToken cancellationToken = default)
    {
        using var scope = services.CreateScope();
        var logger = scope.ServiceProvider
            .GetRequiredService<ILoggerFactory>()
            .CreateLogger("JemNexus.Api.Data.SeedData");
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var options = scope.ServiceProvider.GetRequiredService<IOptions<SeedUserOptions>>().Value;

        var sellerCreated = await SeedUserAsync(
            dbContext,
            passwordHasher,
            logger,
            seedName: "seller",
            username: options.SellerUsername,
            password: options.SellerPassword,
            email: options.SellerEmail,
            fullName: options.SellerFullName,
            role: AppRoles.Seller,
            isStaff: true,
            isSuperuser: false,
            cancellationToken);

        var supportCreated = await SeedUserAsync(
            dbContext,
            passwordHasher,
            logger,
            seedName: "support",
            username: options.SupportUsername,
            password: options.SupportPassword,
            email: options.SupportEmail,
            fullName: options.SupportFullName,
            role: AppRoles.SupportAdmin,
            isStaff: true,
            isSuperuser: false,
            cancellationToken);

        if (sellerCreated || supportCreated)
        {
            await dbContext.SaveChangesAsync(cancellationToken);
        }
    }

    private static async Task<bool> SeedUserAsync(
        JemNexusDbContext dbContext,
        IPasswordHasherService passwordHasher,
        ILogger logger,
        string seedName,
        string username,
        string password,
        string email,
        string fullName,
        string role,
        bool isStaff,
        bool isSuperuser,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
        {
            logger.LogInformation("SeedUsers {SeedName} skipped: missing username/password.", seedName);
            return false;
        }

        var normalizedUsername = username.Trim();
        var usernameAlreadyPending = dbContext.AppUsers.Local
            .Any(user => string.Equals(user.Username, normalizedUsername, StringComparison.Ordinal));
        var existingUser = usernameAlreadyPending
            ? new AppUser()
            : await dbContext.AppUsers
                .AsNoTracking()
                .FirstOrDefaultAsync(user => user.Username == normalizedUsername, cancellationToken);

        if (existingUser is not null)
        {
            logger.LogInformation("SeedUsers {SeedName} already exists.", seedName);
            return false;
        }

        var user = new AppUser
        {
            Username = normalizedUsername,
            Email = string.IsNullOrWhiteSpace(email) ? null : email.Trim(),
            Role = role,
            FullName = string.IsNullOrWhiteSpace(fullName) ? null : fullName.Trim(),
            IsActive = true,
            IsStaff = isStaff,
            IsSuperuser = isSuperuser
        };
        user.PasswordHash = passwordHasher.HashPassword(user, password);

        dbContext.AppUsers.Add(user);
        logger.LogInformation("SeedUsers {SeedName} created.", seedName);
        return true;
    }
}
