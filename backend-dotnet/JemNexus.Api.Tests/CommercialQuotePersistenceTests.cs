using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialQuotePersistenceTests
{
    [Theory]
    [InlineData("CLP", 1000, 1190)]
    [InlineData("USD", 10.25, 12.20)]
    public async Task PersistsDraftWithCalculatedItemsAndSellerSnapshot(string currency, decimal price, decimal expected)
    {
        var options = InMemoryTestDatabase.CreateOptions($"quote-{currency}");
        await using (var db = new JemNexusDbContext(options))
        {
            var seller = new AppUser { Username = "seller", PasswordHash = "hash", SellerCode = "VEN-0001", FullName = "Original" }; db.AppUsers.Add(seller); await db.SaveChangesAsync();
            var quote = CommercialQuoteCalculatorTests.ValidQuote(currency); quote.ResponsibleSellerId = seller.Id; quote.Items.Add(CommercialQuoteCalculatorTests.Item(1, 1, price)); CommercialQuoteCalculator.Calculate(quote); db.CommercialQuotes.Add(quote); await db.SaveChangesAsync();
        }
        await using var verify = new JemNexusDbContext(options); var saved = await verify.CommercialQuotes.Include(q => q.Items).SingleAsync(); Assert.Equal(expected, saved.TotalAmount); Assert.Equal("VEN-0001", saved.ResponsibleSellerCode); Assert.Single(saved.Items); Assert.Equal(currency == "CLP" ? 0m : 0.20m, saved.TotalAmount % 1m);
    }

    [Fact]
    public async Task PersistsEmptyDraftWithoutCustomerProfile()
    {
        var options = InMemoryTestDatabase.CreateOptions("empty-quote"); await using var db = new JemNexusDbContext(options); var seller = new AppUser { Username = "s", PasswordHash = "h", SellerCode = "VEN-0002" }; db.AppUsers.Add(seller); await db.SaveChangesAsync(); var quote = CommercialQuoteCalculatorTests.ValidQuote(); quote.ResponsibleSellerId = seller.Id; CommercialQuoteCalculator.Calculate(quote); db.Add(quote); await db.SaveChangesAsync(); Assert.Null(quote.CustomerProfileId); Assert.Empty(quote.Items); Assert.Equal(0m, quote.TotalAmount); Assert.NotEqual(default, quote.CreatedAt);
    }

    [Fact]
    public async Task SnapshotsRemainWhenLinkedRecordsChange()
    {
        var options = InMemoryTestDatabase.CreateOptions("snapshot-quote"); await using var db = new JemNexusDbContext(options); var seller = new AppUser { Username = "s", PasswordHash = "h", SellerCode = "VEN-0003" }; var customer = new CustomerProfile { BusinessName = "Original", Rut = "12345678-5", NormalizedRut = "12345678-5", BusinessActivity = "A", Address = "A", Phone = "1", CityOrCommune = "C", ContactName = "N", NormalizedBusinessName = "ORIGINAL" }; db.AddRange(seller, customer); await db.SaveChangesAsync(); var quote = CommercialQuoteCalculatorTests.ValidQuote(); quote.ResponsibleSellerId = seller.Id; quote.CustomerProfileId = customer.Id; CommercialQuoteCalculator.Calculate(quote); db.Add(quote); await db.SaveChangesAsync(); customer.BusinessName = "Changed"; await db.SaveChangesAsync(); Assert.Equal("Cliente", quote.CustomerBusinessName);
    }
}
