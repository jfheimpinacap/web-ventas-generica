using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Metadata;
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
        Assert.Contains("20260816000000_AddSellerCodes", discoveredMigrationIds);
        Assert.DoesNotContain(declaredMigrationIds.GroupBy(id => id, StringComparer.Ordinal), group => group.Count() > 1);
    }

    [Fact]
    public void SellerCodeModelHasSequenceLengthUniqueFilteredIndexAndRoleConstraint()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_SellerCodeMetadataTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var model = context.GetService<IDesignTimeModel>().Model;
        var sequence = model.GetSequences().Single(sequence => sequence.Name == "SellerCodeSequence");
        Assert.Equal(1, sequence.StartValue);
        Assert.Equal(1, sequence.IncrementBy);
        var user = model.FindEntityType(typeof(JemNexus.Api.Models.AppUser))!;
        Assert.Equal(24, user.FindProperty("SellerCode")!.GetMaxLength());
        var index = user.GetIndexes().Single(index => index.Properties.Single().Name == "SellerCode");
        Assert.True(index.IsUnique);
        Assert.Equal("[SellerCode] IS NOT NULL", index.GetFilter());
        Assert.Contains(user.GetCheckConstraints(), constraint => constraint.Name == "CK_AppUsers_Role_SellerCode");
    }

    [Fact]
    public void SellerCodeMigrationScriptBackfillsBeforeEnforcingAndDownRemovesObjects()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_SellerCodeScriptTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260812000000_AddProductMachineWeight", "20260816000000_AddSellerCodes");
        Assert.Contains("CREATE SEQUENCE [SellerCodeSequence]", up);
        Assert.Contains("ORDER BY [Id]", up);
        Assert.Contains("NEXT VALUE FOR [SellerCodeSequence]", up);
        Assert.Contains("WHERE [Role] = 'seller'", up);
        Assert.True(up.IndexOf("UPDATE [AppUsers]", StringComparison.Ordinal) < up.IndexOf("IX_AppUsers_SellerCode", StringComparison.Ordinal));
        Assert.Contains("CK_AppUsers_Role_SellerCode", up);

        var down = migrator.GenerateScript("20260816000000_AddSellerCodes", "20260812000000_AddProductMachineWeight");
        Assert.Contains("DROP CONSTRAINT [CK_AppUsers_Role_SellerCode]", down);
        Assert.Contains("DROP INDEX [IX_AppUsers_SellerCode]", down);
        Assert.Contains("DROP COLUMN [SellerCode]", down);
        Assert.Contains("DROP SEQUENCE [SellerCodeSequence]", down);
    }
}
