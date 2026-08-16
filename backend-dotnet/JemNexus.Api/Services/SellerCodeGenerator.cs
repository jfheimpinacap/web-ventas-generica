using System.Data;
using System.Globalization;
using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace JemNexus.Api.Services;

public sealed class SellerCodeGenerator(JemNexusDbContext dbContext) : ISellerCodeGenerator
{
    public async Task<string> GenerateAsync(CancellationToken cancellationToken = default)
    {
        var connection = dbContext.Database.GetDbConnection();
        var shouldClose = connection.State != ConnectionState.Open;
        if (shouldClose)
        {
            await connection.OpenAsync(cancellationToken);
        }

        try
        {
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT NEXT VALUE FOR [SellerCodeSequence]";
            command.Transaction = dbContext.Database.CurrentTransaction?.GetDbTransaction();
            var result = await command.ExecuteScalarAsync(cancellationToken);
            var value = Convert.ToInt64(result, CultureInfo.InvariantCulture);
            return Format(value);
        }
        finally
        {
            if (shouldClose)
            {
                await connection.CloseAsync();
            }
        }
    }

    public static string Format(long value) => $"VEN-{value.ToString("D4", CultureInfo.InvariantCulture)}";
}
