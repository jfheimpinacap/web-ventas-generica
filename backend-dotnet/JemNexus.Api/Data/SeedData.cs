using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.EntityFrameworkCore;
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
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var options = scope.ServiceProvider.GetRequiredService<IOptions<SeedUserOptions>>().Value;

        await SeedUserAsync(
            dbContext,
            passwordHasher,
            username: options.SellerUsername,
            password: options.SellerPassword,
            email: options.SellerEmail,
            fullName: options.SellerFullName,
            role: AppRoles.Seller,
            isStaff: true,
            isSuperuser: false,
            environment,
            cancellationToken);

        await SeedUserAsync(
            dbContext,
            passwordHasher,
            username: options.SupportUsername,
            password: options.SupportPassword,
            email: options.SupportEmail,
            fullName: options.SupportFullName,
            role: AppRoles.SupportAdmin,
            isStaff: true,
            isSuperuser: false,
            environment,
            cancellationToken);

        await dbContext.SaveChangesAsync(cancellationToken);
    }

    private static async Task SeedUserAsync(
        JemNexusDbContext dbContext,
        IPasswordHasherService passwordHasher,
        string username,
        string password,
        string email,
        string fullName,
        string role,
        bool isStaff,
        bool isSuperuser,
        IHostEnvironment environment,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(username))
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(password))
        {
            if (environment.IsProduction())
            {
                return;
            }

            // Development/Test deliberately skip seed users without configured passwords.
            return;
        }

        var normalizedUsername = username.Trim();
        var exists = await dbContext.AppUsers
            .AnyAsync(user => user.Username == normalizedUsername, cancellationToken);

        if (exists)
        {
            return;
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
    }
}
