using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class MigrationMetadataTests
{
    [Fact]
    public void EveryMigrationClassIsDiscoverableByEfCore()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_MigrationMetadataTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;

        using var context = new JemNexusDbContext(options);
        var discoveredMigrationIds = context.Database.GetMigrations().ToHashSet(StringComparer.Ordinal);
        var migrationTypes = typeof(JemNexusDbContext).Assembly.GetTypes()
            .Where(type => !type.IsAbstract && typeof(Migration).IsAssignableFrom(type))
            .ToArray();

        var declaredMigrationIds = new List<string>();
        foreach (var migrationType in migrationTypes)
        {
            var migrationAttribute = Assert.Single(migrationType.GetCustomAttributes(typeof(MigrationAttribute), false).Cast<MigrationAttribute>());
            var dbContextAttribute = Assert.Single(migrationType.GetCustomAttributes(typeof(DbContextAttribute), false).Cast<DbContextAttribute>());

            Assert.Equal(typeof(JemNexusDbContext), dbContextAttribute.ContextType);
            Assert.Contains(migrationAttribute.Id, discoveredMigrationIds);
            declaredMigrationIds.Add(migrationAttribute.Id);
        }

        Assert.Contains("20260803010000_AddTechnicalSheets", discoveredMigrationIds);
        Assert.Contains("20260810080000_AddProductTechnicalSheetAssociation", discoveredMigrationIds);
        Assert.Contains("20260811000000_AddStructuredMachineryTechnicalData", discoveredMigrationIds);
        Assert.Contains("20260812000000_AddProductMachineWeight", discoveredMigrationIds);
        Assert.Empty(declaredMigrationIds.GroupBy(id => id, StringComparer.Ordinal).Where(group => group.Count() > 1));
    }
}
