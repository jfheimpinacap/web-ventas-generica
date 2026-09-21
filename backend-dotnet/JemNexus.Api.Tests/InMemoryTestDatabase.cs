using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace JemNexus.Api.Tests;

internal static class InMemoryTestDatabase
{
    private static readonly InMemoryDatabaseRoot SharedDatabaseRoot = new();

    public static string CreateDatabaseName(string prefix) => $"{prefix}-{Guid.NewGuid():N}";

    public static InMemoryDatabaseRoot GetSharedDatabaseRoot() => SharedDatabaseRoot;

    public static void Configure(DbContextOptionsBuilder options, string databaseName, InMemoryDatabaseRoot databaseRoot)
    {
        options.UseInMemoryDatabase(databaseName, databaseRoot);
    }

    public static DbContextOptions<JemNexusDbContext> CreateOptions(string databaseName)
    {
        var builder = new DbContextOptionsBuilder<JemNexusDbContext>();
        Configure(builder, databaseName, GetSharedDatabaseRoot());
        return builder.Options;
    }
}
