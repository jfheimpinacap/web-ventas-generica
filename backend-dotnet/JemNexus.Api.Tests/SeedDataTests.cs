using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Options;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class SeedDataTests
{
    [Fact]
    public async Task SeedUsersDoesNotDuplicateUsers()
    {
        var services = CreateServices();
        var environment = new TestHostEnvironment();

        await SeedData.SeedUsersAsync(services, environment);
        await SeedData.SeedUsersAsync(services, environment);

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.Equal(2, await dbContext.AppUsers.CountAsync());
    }

    [Fact]
    public async Task SeedUsersSetsExpectedRolesAndActiveFlag()
    {
        var services = CreateServices();
        var environment = new TestHostEnvironment();

        await SeedData.SeedUsersAsync(services, environment);

        using var scope = services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var seller = await dbContext.AppUsers.SingleAsync(user => user.Username == "demo");
        var support = await dbContext.AppUsers.SingleAsync(user => user.Username == "support");

        Assert.True(seller.IsActive);
        Assert.True(support.IsActive);
        Assert.Equal(AppRoles.Seller, seller.Role);
        Assert.Equal(AppRoles.SupportAdmin, support.Role);
    }

    private static ServiceProvider CreateServices()
    {
        var services = new ServiceCollection();
        services.AddDbContext<JemNexusDbContext>(options => options.UseInMemoryDatabase(Guid.NewGuid().ToString()));
        services.AddScoped<IPasswordHasher<AppUser>, PasswordHasher<AppUser>>();
        services.AddScoped<IPasswordHasherService, PasswordHasherService>();
        services.AddSingleton(Options.Create(new SeedUserOptions
        {
            SellerUsername = "demo",
            SellerPassword = "seller-password",
            SupportUsername = "support",
            SupportPassword = "support-password"
        }));
        return services.BuildServiceProvider();
    }

    private sealed class TestHostEnvironment : IHostEnvironment
    {
        public string EnvironmentName { get; set; } = Environments.Development;
        public string ApplicationName { get; set; } = "JemNexus.Api.Tests";
        public string ContentRootPath { get; set; } = AppContext.BaseDirectory;
        public Microsoft.Extensions.FileProviders.IFileProvider ContentRootFileProvider { get; set; } = null!;
    }
}
