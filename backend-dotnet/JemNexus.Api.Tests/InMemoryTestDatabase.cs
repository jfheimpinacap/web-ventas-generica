using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.EntityFrameworkCore.Storage;

namespace JemNexus.Api.Tests;

internal static class InMemoryTestDatabase
{
    public static string CreateDatabaseName(string prefix) => $"{prefix}-{Guid.NewGuid():N}";

    public static InMemoryDatabaseRoot CreateDatabaseRoot() => new();

    public static void Configure(DbContextOptionsBuilder options, string databaseName, InMemoryDatabaseRoot databaseRoot)
    {
        options
            .UseInMemoryDatabase(databaseName, databaseRoot)
            .ConfigureWarnings(warnings =>
            {
                // Tests intentionally create isolated InMemory stores per factory/service provider.
                // Do not share UseInternalServiceProvider because UseInMemoryDatabase options vary per test database.
                warnings.Ignore(CoreEventId.ManyServiceProvidersCreatedWarning);
            });
    }

    public static DbContextOptions<JemNexusDbContext> CreateOptions(string databaseName)
    {
        var builder = new DbContextOptionsBuilder<JemNexusDbContext>();
        Configure(builder, databaseName, CreateDatabaseRoot());
        return builder.Options;
    }
}
