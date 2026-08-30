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
        Assert.Contains("20260822000000_AddRefreshTokenRotation", discoveredMigrationIds);
        Assert.Contains("20260822010000_AddRefreshTokenPasswordVersion", discoveredMigrationIds);
        Assert.Contains("20260822020000_AddCommercialQuoteIssueIdempotency", discoveredMigrationIds);
        Assert.Contains("20260824010000_AddSellerContactQuoteSnapshots", discoveredMigrationIds);
        Assert.Contains("20260825010000_AddCustomerProfileStatus", discoveredMigrationIds);
        Assert.Contains("20260830000000_PreserveQuotesWhenDeletingProducts", discoveredMigrationIds);
        Assert.DoesNotContain(declaredMigrationIds.GroupBy(id => id, StringComparer.Ordinal), group => group.Count() > 1);
    }

    [Fact]
    public void HistoricalQuoteProductRelationsUseSetNullWithoutChangingSnapshots()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_QuoteProductDeleteMetadataTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var model = context.GetService<IDesignTimeModel>().Model;

        var quoteItemProductForeignKey = model.FindEntityType(typeof(JemNexus.Api.Models.CommercialQuoteItem))!
            .GetForeignKeys().Single(foreignKey => foreignKey.PrincipalEntityType.ClrType == typeof(JemNexus.Api.Models.Product));
        var quoteRequestProductForeignKey = model.FindEntityType(typeof(JemNexus.Api.Models.QuoteRequest))!
            .GetForeignKeys().Single(foreignKey => foreignKey.PrincipalEntityType.ClrType == typeof(JemNexus.Api.Models.Product));

        Assert.False(quoteItemProductForeignKey.IsRequired);
        Assert.False(quoteRequestProductForeignKey.IsRequired);
        Assert.Equal(DeleteBehavior.SetNull, quoteItemProductForeignKey.DeleteBehavior);
        Assert.Equal(DeleteBehavior.SetNull, quoteRequestProductForeignKey.DeleteBehavior);
    }

    [Fact]
    public void CustomerStatusMigrationOnlyAddsAndRemovesRequiredActiveColumn()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_CustomerStatusScriptTests;Trusted_Connection=True;TrustServerCertificate=True").Options;
        using var context = new JemNexusDbContext(options);
        var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260824010000_AddSellerContactQuoteSnapshots", "20260825010000_AddCustomerProfileStatus");
        Assert.Contains("ALTER TABLE [CustomerProfiles] ADD [IsActive] bit NOT NULL DEFAULT CAST(1 AS bit)", up);
        Assert.DoesNotContain("CommercialQuotes", up);
        Assert.DoesNotContain("CREATE INDEX", up);

        var down = migrator.GenerateScript("20260825010000_AddCustomerProfileStatus", "20260824010000_AddSellerContactQuoteSnapshots");
        Assert.Contains("ALTER TABLE [CustomerProfiles] DROP COLUMN [IsActive]", down);
        Assert.DoesNotContain("CommercialQuotes", down);
    }


    [Fact]
    public void SellerContactSnapshotMigrationAddsBackfillsAndDropsOnlyExpectedColumns()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_SellerContactScriptTests;Trusted_Connection=True;TrustServerCertificate=True").Options;
        using var context = new JemNexusDbContext(options);
        var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260822020000_AddCommercialQuoteIssueIdempotency", "20260824010000_AddSellerContactQuoteSnapshots");
        Assert.Contains("ADD [Phone] nvarchar(32) NULL", up);
        Assert.Contains("ADD [ResponsibleSellerEmail] nvarchar(254) NULL", up);
        Assert.Contains("ADD [ResponsibleSellerPhone] nvarchar(32) NULL", up);
        Assert.Contains("jmateluna@jem-nexus.cl", up); Assert.Contains("+56 9 4611 5064", up);
        Assert.Contains("[Phone] IS NULL OR LTRIM(RTRIM([Phone]))", up);
        Assert.Contains("INNER JOIN [AppUsers]", up);
        foreach (var forbidden in new[] { "Currency", "NetAmount", "TotalAmount", "Folio", "CommercialQuoteItems", "AppRefreshTokens", "IdempotencyKey" })
            Assert.DoesNotContain(forbidden, up);

        var down = migrator.GenerateScript("20260824010000_AddSellerContactQuoteSnapshots", "20260822020000_AddCommercialQuoteIssueIdempotency");
        Assert.Contains("DROP COLUMN [ResponsibleSellerPhone]", down);
        Assert.Contains("DROP COLUMN [ResponsibleSellerEmail]", down);
        Assert.Contains("DROP COLUMN [Phone]", down);
    }

    [Fact]
    public void RefreshTokenModelHasRotationFamilyAndConcurrencyMetadata()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_RefreshTokenMetadataTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var model = context.GetService<IDesignTimeModel>().Model;
        var token = model.FindEntityType(typeof(JemNexus.Api.Models.AppRefreshToken))!;
        var family = token.FindProperty("FamilyId")!;
        var replacement = token.FindProperty("ReplacedByTokenHash")!;
        var passwordVersion = token.FindProperty("PasswordVersion")!;

        Assert.False(family.IsNullable);
        Assert.Equal("NEWID()", family.GetDefaultValueSql());
        Assert.True(replacement.IsNullable);
        Assert.Equal(128, replacement.GetMaxLength());
        Assert.True(passwordVersion.IsNullable);
        Assert.Equal(128, passwordVersion.GetMaxLength());
        Assert.DoesNotContain(token.GetIndexes(), index => index.Properties.Any(property => property.Name == "PasswordVersion"));
        Assert.True(token.FindProperty("RevokedAt")!.IsConcurrencyToken);
        Assert.Contains(token.GetIndexes(), index => !index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(["FamilyId"]));
        Assert.Contains(token.GetIndexes(), index => index.IsUnique && index.Properties.Select(property => property.Name).SequenceEqual(["TokenHash"]));
    }

    [Fact]
    public void CommercialQuoteIssueIdempotencyMigrationCreatesAndDropsOnlyIdempotencyTable()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_QuoteIdempotencyScriptTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options); var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260822010000_AddRefreshTokenPasswordVersion", "20260822020000_AddCommercialQuoteIssueIdempotency");
        Assert.Contains("CREATE TABLE [CommercialQuoteIssueIdempotencyRecords]", up);
        Assert.Contains("[ResponsibleSellerId] int NOT NULL", up); Assert.Contains("[IdempotencyKey] uniqueidentifier NOT NULL", up);
        Assert.Contains("[RequestFingerprint] nvarchar(64) NOT NULL", up); Assert.Contains("[CommercialQuoteId] int NOT NULL", up); Assert.Contains("[CreatedAt] datetimeoffset NOT NULL", up);
        Assert.Contains("PRIMARY KEY ([ResponsibleSellerId], [IdempotencyKey])", up);
        Assert.Contains("REFERENCES [AppUsers] ([Id])", up); Assert.Contains("REFERENCES [CommercialQuotes] ([Id])", up);
        Assert.Contains("CREATE UNIQUE INDEX [UX_CommercialQuoteIssueIdempotencyRecords_CommercialQuoteId]", up);
        Assert.DoesNotContain("ALTER TABLE [CommercialQuotes]", up); Assert.DoesNotContain("ALTER TABLE [AppRefreshTokens]", up);
        Assert.DoesNotContain("CommercialQuoteFolioCounters", up); Assert.DoesNotContain("CommercialQuoteItems", up);

        var down = migrator.GenerateScript("20260822020000_AddCommercialQuoteIssueIdempotency", "20260822010000_AddRefreshTokenPasswordVersion");
        Assert.Contains("DROP TABLE [CommercialQuoteIssueIdempotencyRecords]", down);
        Assert.DoesNotContain("DROP COLUMN", down); Assert.DoesNotContain("ALTER TABLE [CommercialQuotes]", down);
        Assert.DoesNotContain("ALTER TABLE [AppRefreshTokens]", down); Assert.DoesNotContain("CommercialQuoteFolioCounters", down);
    }

    [Fact]
    public void RefreshTokenPasswordVersionMigrationOnlyAddsAndRemovesNullableColumn()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_PasswordVersionScriptTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260822000000_AddRefreshTokenRotation", "20260822010000_AddRefreshTokenPasswordVersion");
        Assert.Contains("ADD [PasswordVersion] nvarchar(128) NULL", up);
        Assert.DoesNotContain("FamilyId", up);

        var down = migrator.GenerateScript("20260822010000_AddRefreshTokenPasswordVersion", "20260822000000_AddRefreshTokenRotation");
        Assert.Contains("DROP COLUMN [PasswordVersion]", down);
        Assert.DoesNotContain("FamilyId", down);
    }

    [Fact]
    public void RefreshTokenRotationMigrationScriptAddsAndRemovesFamilyMetadata()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=JemNexus_RefreshTokenScriptTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;
        using var context = new JemNexusDbContext(options);
        var migrator = context.GetService<IMigrator>();
        var up = migrator.GenerateScript("20260816000000_AddSellerCodes", "20260822000000_AddRefreshTokenRotation");
        Assert.Contains("[FamilyId] uniqueidentifier NOT NULL DEFAULT (NEWID())", up);
        Assert.Contains("[ReplacedByTokenHash] nvarchar(128) NULL", up);
        Assert.Contains("IX_AppRefreshTokens_FamilyId", up);

        var down = migrator.GenerateScript("20260822000000_AddRefreshTokenRotation", "20260816000000_AddSellerCodes");
        Assert.True(down.IndexOf("DROP INDEX [IX_AppRefreshTokens_FamilyId]", StringComparison.Ordinal)
            < down.IndexOf("DROP COLUMN [ReplacedByTokenHash]", StringComparison.Ordinal));
        Assert.True(down.IndexOf("DROP COLUMN [ReplacedByTokenHash]", StringComparison.Ordinal)
            < down.IndexOf("DROP COLUMN [FamilyId]", StringComparison.Ordinal));
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
