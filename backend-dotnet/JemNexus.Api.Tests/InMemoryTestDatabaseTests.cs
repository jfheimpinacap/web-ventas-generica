using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class InMemoryTestDatabaseTests
{
    [Fact]
    public async Task SharedRootSupportsMoreThanTwentyIsolatedDatabases()
    {
        const int databaseCount = 25;
        var names = Enumerable.Range(0, databaseCount)
            .Select(index => InMemoryTestDatabase.CreateDatabaseName($"shared-root-{index}"))
            .ToArray();
        var contexts = names
            .Select(name => new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(name)))
            .ToArray();

        try
        {
            Assert.Equal(databaseCount, names.Distinct(StringComparer.Ordinal).Count());
            Assert.Same(
                InMemoryTestDatabase.GetSharedDatabaseRoot(),
                InMemoryTestDatabase.GetSharedDatabaseRoot());

            contexts[0].AppUsers.Add(new AppUser
            {
                Username = "isolated-user",
                PasswordHash = "not-a-real-password-hash",
                SellerCode = "VEN-ISOLATED",
                Role = AppRoles.Seller,
                IsStaff = true,
                IsActive = true
            });
            await contexts[0].SaveChangesAsync();

            Assert.Equal(1, await contexts[0].AppUsers.CountAsync());
            foreach (var context in contexts.Skip(1))
                Assert.Empty(await context.AppUsers.ToListAsync());
        }
        finally
        {
            foreach (var context in contexts)
                await context.DisposeAsync();
        }
    }
}
