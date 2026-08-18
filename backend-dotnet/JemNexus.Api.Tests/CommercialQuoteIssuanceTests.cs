using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialQuoteIssuanceTests
{
    [Fact]
    public void DraftHasNoIssuanceDataAndCanOnlyBeIssuedOnce()
    {
        var quote = CommercialQuoteCalculatorTests.ValidQuote();
        quote.Items.Add(CommercialQuoteCalculatorTests.Item(1));
        CommercialQuoteCalculator.Calculate(quote);
        Assert.Null(quote.Folio);
        quote.Issue(2026, 1, new DateTime(2026, 8, 17, 15, 30, 0, DateTimeKind.Utc), new DateOnly(2026, 8, 17));
        Assert.Equal(CommercialQuoteStatuses.Issued, quote.Status);
        Assert.Equal("COT-2026-000001", quote.Folio);
        Assert.Equal(1, quote.FolioSequenceNumber);
        Assert.Throws<InvalidOperationException>(() => quote.Issue(2026, 2, new DateTime(2026, 8, 17, 15, 31, 0, DateTimeKind.Utc), new DateOnly(2026, 8, 17)));
    }

    [Fact]
    public void FolioWidthIsAMinimumRatherThanATruncation()
    {
        var quote = CommercialQuoteCalculatorTests.ValidQuote();
        quote.Issue(2026, 1_000_000, new DateTime(2026, 1, 1, 4, 0, 0, DateTimeKind.Utc), new DateOnly(2026, 1, 1));
        Assert.Equal("COT-2026-1000000", quote.Folio);
    }

    [Fact]
    public void ChileanCalendarDeterminesTheYearNearUtcNewYear()
    {
        var time = new FixedTimeProvider(new DateTimeOffset(2027, 1, 1, 2, 30, 0, TimeSpan.Zero));
        var (utc, localDate) = ChileTime.Current(time);
        Assert.Equal(DateTimeKind.Utc, utc.Kind);
        Assert.Equal(new DateOnly(2026, 12, 31), localDate);
    }

    [Fact]
    public void ModelHasFilteredUniqueIndexesAndAnnualCounterKey()
    {
        using var db = new JemNexusDbContext(new DbContextOptionsBuilder<JemNexusDbContext>().UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=metadata").Options);
        var quote = db.Model.FindEntityType(typeof(CommercialQuote))!;
        var folio = quote.GetIndexes().Single(index => index.GetDatabaseName() == "UX_CommercialQuotes_Folio");
        var sequence = quote.GetIndexes().Single(index => index.GetDatabaseName() == "UX_CommercialQuotes_FolioYear_Sequence");
        Assert.True(folio.IsUnique); Assert.Equal("[Folio] IS NOT NULL", folio.GetFilter());
        Assert.True(sequence.IsUnique); Assert.Equal("[FolioYear] IS NOT NULL AND [FolioSequenceNumber] IS NOT NULL", sequence.GetFilter());
        Assert.Equal(nameof(CommercialQuoteFolioCounter.Year), db.Model.FindEntityType(typeof(CommercialQuoteFolioCounter))!.FindPrimaryKey()!.Properties.Single().Name);
    }

    private sealed class FixedTimeProvider(DateTimeOffset value) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => value;
    }
}
