using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.DependencyInjection;

namespace JemNexus.Api.Tests;

internal static class InMemoryTestDatabase
{
    private static readonly ServiceProvider InternalServiceProvider = new ServiceCollection()
        .AddEntityFrameworkInMemoryDatabase()
        .BuildServiceProvider();

    public static void Configure(DbContextOptionsBuilder options, string databaseName, InMemoryDatabaseRoot databaseRoot)
    {
        options
            .UseInMemoryDatabase(databaseName, databaseRoot)
            .UseInternalServiceProvider(InternalServiceProvider);
    }

    public static DbContextOptions<JemNexusDbContext> CreateOptions(string databaseName)
    {
        var builder = new DbContextOptionsBuilder<JemNexusDbContext>();
        Configure(builder, databaseName, new InMemoryDatabaseRoot());
        return builder.Options;
    }
}
