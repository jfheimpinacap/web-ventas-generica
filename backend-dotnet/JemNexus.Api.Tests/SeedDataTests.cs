using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class SeedDataTests
{
    [Fact]
    public async Task SeedUsersCreatesSellerWhenUsernameAndPasswordAreConfigured()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = "  demo  ";
            options.SellerPassword = "DummyPassword123!";
            options.SupportUsername = string.Empty;
            options.SupportPassword = string.Empty;
        });
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Production };

        await SeedData.SeedUsersAsync(services, environment);

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var seller = await dbContext.AppUsers.SingleAsync();
        Assert.Equal("demo", seller.Username);
        Assert.Equal(AppRoles.Seller, seller.Role);
        Assert.True(seller.IsActive);
        Assert.True(seller.IsStaff);
        Assert.False(seller.IsSuperuser);
    }

    [Fact]
    public async Task SeedUsersCreatesSupportWhenUsernameAndPasswordAreConfigured()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = string.Empty;
            options.SellerPassword = string.Empty;
            options.SupportUsername = "  support  ";
            options.SupportPassword = "DummyPassword123!";
        });
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Production };

        await SeedData.SeedUsersAsync(services, environment);

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var support = await dbContext.AppUsers.SingleAsync();
        Assert.Equal("support", support.Username);
        Assert.Equal(AppRoles.SupportAdmin, support.Role);
        Assert.True(support.IsActive);
        Assert.True(support.IsStaff);
        Assert.False(support.IsSuperuser);
    }

    [Fact]
    public async Task SeedUsersDoesNotCreateUsersWhenPasswordIsMissing()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = "demo";
            options.SellerPassword = string.Empty;
            options.SupportUsername = "support";
            options.SupportPassword = "   ";
        });
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Production };

        await SeedData.SeedUsersAsync(services, environment);

        await AssertSeededUsersCountAsync(services, expectedCount: 0);
    }

    [Fact]
    public async Task SeedUsersDoesNotDuplicateUsers()
    {
        using var services = CreateServices();
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Production };

        await SeedData.SeedUsersAsync(services, environment);
        await AssertSeededUsersCountAsync(services, expectedCount: 2);

        await SeedData.SeedUsersAsync(services, environment);
        await AssertSeededUsersCountAsync(services, expectedCount: 2);
    }

    [Fact]
    public async Task SeedUsersDoesNotOverwriteExistingPasswordHash()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = "demo";
            options.SellerPassword = "NewPassword123!";
            options.SupportUsername = string.Empty;
            options.SupportPassword = string.Empty;
        });
        const string originalHash = "existing-password-hash";

        using (var scope = services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            dbContext.AppUsers.Add(new AppUser
            {
                Username = "demo",
                PasswordHash = originalHash,
                Role = AppRoles.Seller,
                IsActive = true,
                IsStaff = true,
                IsSuperuser = false
            });
            await dbContext.SaveChangesAsync();
        }

        await SeedData.SeedUsersAsync(services, new TestHostEnvironment { EnvironmentName = Environments.Production });

        using (var scope = services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var seller = await dbContext.AppUsers.SingleAsync(user => user.Username == "demo");
            Assert.Equal(originalHash, seller.PasswordHash);
        }
    }

    [Fact]
    public async Task SeedUsersUpdatesExistingPasswordWhenExplicitFlagIsEnabled()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = "demo";
            options.SellerPassword = "NewPassword123!";
            options.SupportUsername = string.Empty;
            options.SupportPassword = string.Empty;
            options.UpdateExistingPasswords = true;
        });
        const string oldPassword = "OldPassword123!";

        await AddUserWithPasswordAsync(services, "demo", oldPassword, AppRoles.Seller);

        await SeedData.SeedUsersAsync(services, new TestHostEnvironment { EnvironmentName = Environments.Production });

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var seller = await dbContext.AppUsers.SingleAsync(user => user.Username == "demo");

        Assert.True(passwordHasher.VerifyPassword(seller, "NewPassword123!"));
        Assert.False(passwordHasher.VerifyPassword(seller, oldPassword));
        Assert.Equal(AppRoles.Seller, seller.Role);
        Assert.True(seller.IsActive);
        Assert.True(seller.IsStaff);
        Assert.False(seller.IsSuperuser);
    }

    [Fact]
    public async Task SeedUsersDoesNotUpdateExistingPasswordWhenExplicitFlagIsEnabledButPasswordIsMissing()
    {
        using var services = CreateServices(options =>
        {
            options.SellerUsername = "demo";
            options.SellerPassword = string.Empty;
            options.SupportUsername = string.Empty;
            options.SupportPassword = string.Empty;
            options.UpdateExistingPasswords = true;
        });
        const string oldPassword = "OldPassword123!";

        await AddUserWithPasswordAsync(services, "demo", oldPassword, AppRoles.Seller);

        await SeedData.SeedUsersAsync(services, new TestHostEnvironment { EnvironmentName = Environments.Production });

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var seller = await dbContext.AppUsers.SingleAsync(user => user.Username == "demo");

        Assert.True(passwordHasher.VerifyPassword(seller, oldPassword));
        Assert.False(passwordHasher.VerifyPassword(seller, "NewPassword123!"));
    }

    [Fact]
    public async Task SeedUsersDoesNotWritePasswordsToLogsWhenUpdatingExistingPassword()
    {
        var logProvider = new CapturingLoggerProvider();
        using var services = CreateServices(
            options =>
            {
                options.SellerUsername = "demo";
                options.SellerPassword = "NewPassword123!";
                options.SupportUsername = string.Empty;
                options.SupportPassword = string.Empty;
                options.UpdateExistingPasswords = true;
            },
            logProvider);
        const string oldPassword = "OldPassword123!";

        await AddUserWithPasswordAsync(services, "demo", oldPassword, AppRoles.Seller);

        await SeedData.SeedUsersAsync(services, new TestHostEnvironment { EnvironmentName = Environments.Production });

        Assert.Contains("SeedUsers seller password updated.", logProvider.Messages);
        Assert.DoesNotContain(logProvider.Messages, message => message.Contains("NewPassword123!", StringComparison.Ordinal));
        Assert.DoesNotContain(logProvider.Messages, message => message.Contains(oldPassword, StringComparison.Ordinal));
    }

    [Fact]
    public async Task SeedUsersSetsExpectedRolesAndActiveFlag()
    {
        using var services = CreateServices();
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Development };

        await SeedData.SeedUsersAsync(services, environment);
        await AssertSeededUsersCountAsync(services, expectedCount: 2);

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var seller = await dbContext.AppUsers.SingleAsync(user => user.Username == "demo");
        var support = await dbContext.AppUsers.SingleAsync(user => user.Username == "support");

        Assert.True(seller.IsActive);
        Assert.True(support.IsActive);
        Assert.Equal(AppRoles.Seller, seller.Role);
        Assert.Equal(AppRoles.SupportAdmin, support.Role);
        Assert.True(seller.IsStaff);
        Assert.True(support.IsStaff);
        Assert.False(seller.IsSuperuser);
        Assert.False(support.IsSuperuser);
    }

    [Fact]
    public async Task SeedUsersRunsInProductionWhenVariablesExist()
    {
        using var services = CreateServices();
        var environment = new TestHostEnvironment { EnvironmentName = Environments.Production };

        await SeedData.SeedUsersAsync(services, environment);

        await AssertSeededUsersCountAsync(services, expectedCount: 2);
    }

    private static ServiceProvider CreateServices(
        Action<SeedUserOptions>? configureSeedUsers = null,
        ILoggerProvider? loggerProvider = null)
    {
        var services = new ServiceCollection();
        var databaseName = InMemoryTestDatabase.CreateDatabaseName("SeedDataTests");
        var databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();

        services.AddLogging(builder =>
        {
            if (loggerProvider is not null)
            {
                builder.AddProvider(loggerProvider);
            }
        });
        services.AddDbContext<JemNexusDbContext>(options =>
            InMemoryTestDatabase.Configure(options, databaseName, databaseRoot));
        services.AddScoped<IPasswordHasher<AppUser>, PasswordHasher<AppUser>>();
        services.AddScoped<IPasswordHasherService, PasswordHasherService>();
        services.AddOptions<SeedUserOptions>()
            .Configure(options =>
            {
                options.SellerUsername = "demo";
                options.SellerPassword = "DummyPassword123!";
                options.SupportUsername = "support";
                options.SupportPassword = "DummyPassword123!";
                configureSeedUsers?.Invoke(options);
            });
        return services.BuildServiceProvider();
    }

    private static async Task AddUserWithPasswordAsync(
        IServiceProvider services,
        string username,
        string password,
        string role)
    {
        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var passwordHasher = scope.ServiceProvider.GetRequiredService<IPasswordHasherService>();
        var user = new AppUser
        {
            Username = username,
            Role = role,
            IsActive = true,
            IsStaff = true,
            IsSuperuser = false
        };
        user.PasswordHash = passwordHasher.HashPassword(user, password);
        dbContext.AppUsers.Add(user);
        await dbContext.SaveChangesAsync();
    }

    private static async Task AssertSeededUsersCountAsync(IServiceProvider services, int expectedCount)
    {
        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.Equal(expectedCount, await dbContext.AppUsers.CountAsync());
    }

    private sealed class CapturingLoggerProvider : ILoggerProvider
    {
        private readonly List<string> messages = new();

        public IReadOnlyList<string> Messages => messages;

        public ILogger CreateLogger(string categoryName)
        {
            return new CapturingLogger(messages);
        }

        public void Dispose()
        {
        }
    }

    private sealed class CapturingLogger(List<string> messages) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state)
            where TState : notnull
        {
            return null;
        }

        public bool IsEnabled(LogLevel logLevel)
        {
            return true;
        }

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            messages.Add(formatter(state, exception));
        }
    }

    private sealed class TestHostEnvironment : IHostEnvironment
    {
        public string EnvironmentName { get; set; } = Environments.Development;
        public string ApplicationName { get; set; } = "JemNexus.Api.Tests";
        public string ContentRootPath { get; set; } = AppContext.BaseDirectory;
        public Microsoft.Extensions.FileProviders.IFileProvider ContentRootFileProvider { get; set; } = null!;
    }
}
