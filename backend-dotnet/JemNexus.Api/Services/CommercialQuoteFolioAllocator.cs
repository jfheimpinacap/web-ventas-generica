using System.Data;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Services;

public static class CommercialQuoteFolioAllocator
{
    public static async Task<long> NextAsync(JemNexusDbContext db, int year, CancellationToken ct)
    {
        CommercialQuoteFolioCounter? counter;
        if (db.Database.IsSqlServer())
        {
            counter = await db.CommercialQuoteFolioCounters
                .FromSqlInterpolated($"SELECT * FROM [CommercialQuoteFolioCounters] WITH (UPDLOCK, HOLDLOCK) WHERE [Year] = {year}")
                .SingleOrDefaultAsync(ct);
        }
        else counter = await db.CommercialQuoteFolioCounters.SingleOrDefaultAsync(value => value.Year == year, ct);

        if (counter is null)
        {
            counter = new CommercialQuoteFolioCounter { Year = year, LastNumber = 1 };
            db.CommercialQuoteFolioCounters.Add(counter);
        }
        else counter.LastNumber = checked(counter.LastNumber + 1);
        return counter.LastNumber;
    }

    public static IsolationLevel SqlServerIsolationLevel => IsolationLevel.Serializable;
}
