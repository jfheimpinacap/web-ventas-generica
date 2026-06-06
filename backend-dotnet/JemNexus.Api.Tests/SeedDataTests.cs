using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
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

    private static ServiceProvider CreateServices(Action<SeedUserOptions>? configureSeedUsers = null)
    {
        var services = new ServiceCollection();
        var databaseName = $"SeedDataTests-{Guid.NewGuid():N}";
        var databaseRoot = new InMemoryDatabaseRoot();

        services.AddLogging();
        services.AddDbContext<JemNexusDbContext>(options =>
            options.UseInMemoryDatabase(databaseName, databaseRoot));
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

    private static async Task AssertSeededUsersCountAsync(IServiceProvider services, int expectedCount)
    {
        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.Equal(expectedCount, await dbContext.AppUsers.CountAsync());
    }

    private sealed class TestHostEnvironment : IHostEnvironment
    {
        public string EnvironmentName { get; set; } = Environments.Development;
        public string ApplicationName { get; set; } = "JemNexus.Api.Tests";
        public string ContentRootPath { get; set; } = AppContext.BaseDirectory;
        public Microsoft.Extensions.FileProviders.IFileProvider ContentRootFileProvider { get; set; } = null!;
    }
}
