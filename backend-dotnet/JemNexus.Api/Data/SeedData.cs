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
        var sellerCodeGenerator = scope.ServiceProvider.GetRequiredService<ISellerCodeGenerator>();
        var options = scope.ServiceProvider.GetRequiredService<IOptions<SeedUserOptions>>().Value;

        var sellerCreated = await SeedUserAsync(
            dbContext,
            passwordHasher,
            sellerCodeGenerator,
            logger,
            seedName: "seller",
            username: options.SellerUsername,
            password: options.SellerPassword,
            email: options.SellerEmail,
            phone: options.SellerPhone,
            fullName: options.SellerFullName,
            role: AppRoles.Seller,
            isStaff: true,
            isSuperuser: false,
            updateExistingPassword: options.UpdateExistingPasswords,
            cancellationToken);

        var supportCreated = await SeedUserAsync(
            dbContext,
            passwordHasher,
            sellerCodeGenerator,
            logger,
            seedName: "support",
            username: options.SupportUsername,
            password: options.SupportPassword,
            email: options.SupportEmail,
            phone: null,
            fullName: options.SupportFullName,
            role: AppRoles.SupportAdmin,
            isStaff: true,
            isSuperuser: false,
            updateExistingPassword: options.UpdateExistingPasswords,
            cancellationToken);

        var permissionChanges = await EnsureSellerPermissionsAsync(dbContext, cancellationToken);
        if (sellerCreated || supportCreated || permissionChanges)
        {
            await dbContext.SaveChangesAsync(cancellationToken);
        }
    }

    private static async Task<bool> EnsureSellerPermissionsAsync(JemNexusDbContext dbContext, CancellationToken cancellationToken)
    {
        var sellers = await dbContext.AppUsers.Include(user => user.Permissions)
            .Where(user => user.Role == AppRoles.Seller).ToListAsync(cancellationToken);
        var before = dbContext.ChangeTracker.Entries<AppUserPermission>().Count(entry => entry.State == EntityState.Added);
        foreach (var seller in sellers) DefaultSellerPermissions.EnsureAssigned(seller);
        return dbContext.ChangeTracker.Entries<AppUserPermission>().Count(entry => entry.State == EntityState.Added) > before;
    }

    private static async Task<bool> SeedUserAsync(
        JemNexusDbContext dbContext,
        IPasswordHasherService passwordHasher,
        ISellerCodeGenerator sellerCodeGenerator,
        ILogger logger,
        string seedName,
        string username,
        string password,
        string email,
        string? phone,
        string fullName,
        string role,
        bool isStaff,
        bool isSuperuser,
        bool updateExistingPassword,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
        {
            logger.LogInformation("SeedUsers {SeedName} skipped: missing username/password.", seedName);
            return false;
        }

        var normalizedUsername = username.Trim();
        var existingUser = dbContext.AppUsers.Local
            .FirstOrDefault(user => string.Equals(user.Username, normalizedUsername, StringComparison.Ordinal));
        existingUser ??= await dbContext.AppUsers.Include(user => user.Permissions)
            .FirstOrDefaultAsync(user => user.Username == normalizedUsername, cancellationToken);

        if (existingUser is not null)
        {
            var changed = false;
            var permissionCount = existingUser.Permissions.Count;
            DefaultSellerPermissions.EnsureAssigned(existingUser);
            changed |= existingUser.Permissions.Count != permissionCount;
            if (role == AppRoles.Seller && existingUser.SellerCode is null)
            {
                existingUser.SellerCode = await sellerCodeGenerator.GenerateAsync(cancellationToken);
                changed = true;
            }
            else if (role != AppRoles.Seller && existingUser.SellerCode is not null)
            {
                existingUser.SellerCode = null;
                changed = true;
            }

            if (!updateExistingPassword)
            {
                logger.LogInformation("SeedUsers {SeedName} already exists.", seedName);
                return changed;
            }

            existingUser.PasswordHash = passwordHasher.HashPassword(existingUser, password);
            logger.LogInformation("SeedUsers {SeedName} password updated.", seedName);
            return true;
        }

        var user = new AppUser
        {
            Username = normalizedUsername,
            Email = string.IsNullOrWhiteSpace(email) ? null : email.Trim(),
            Phone = string.IsNullOrWhiteSpace(phone) ? null : phone.Trim(),
            Role = role,
            SellerCode = role == AppRoles.Seller
                ? await sellerCodeGenerator.GenerateAsync(cancellationToken)
                : null,
            FullName = string.IsNullOrWhiteSpace(fullName) ? null : fullName.Trim(),
            IsActive = true,
            IsStaff = isStaff,
            IsSuperuser = isSuperuser
        };
        user.PasswordHash = passwordHasher.HashPassword(user, password);
        DefaultSellerPermissions.EnsureAssigned(user);

        dbContext.AppUsers.Add(user);
        logger.LogInformation("SeedUsers {SeedName} created.", seedName);
        return true;
    }
}
