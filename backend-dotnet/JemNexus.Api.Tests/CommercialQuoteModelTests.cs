using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialQuoteModelTests
{
    [Fact]
    public void ModelDefinesQuoteRelationshipsAndPrecision()
    {
        using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions("quote-model")); var quote = db.Model.FindEntityType(typeof(CommercialQuote))!; var item = db.Model.FindEntityType(typeof(CommercialQuoteItem))!;
        Assert.Equal(nameof(CommercialQuote.Id), quote.FindPrimaryKey()!.Properties.Single().Name); Assert.True(quote.FindProperty(nameof(CommercialQuote.CustomerProfileId))!.IsNullable); Assert.False(quote.FindProperty(nameof(CommercialQuote.ResponsibleSellerId))!.IsNullable); Assert.True(item.FindProperty(nameof(CommercialQuoteItem.ProductId))!.IsNullable);
        Assert.Equal(DeleteBehavior.Cascade, item.GetForeignKeys().Single(f => f.PrincipalEntityType.ClrType == typeof(CommercialQuote)).DeleteBehavior); Assert.All(item.GetForeignKeys().Where(f => f.PrincipalEntityType.ClrType != typeof(CommercialQuote)), f => Assert.NotEqual(DeleteBehavior.Cascade, f.DeleteBehavior));
        Assert.True(item.GetIndexes().Single(i => i.Properties.Select(p => p.Name).SequenceEqual(new[] { nameof(CommercialQuoteItem.CommercialQuoteId), nameof(CommercialQuoteItem.Position) })).IsUnique);
        Assert.Equal(18, item.FindProperty(nameof(CommercialQuoteItem.UnitNetAmount))!.GetPrecision()); Assert.Equal(2, item.FindProperty(nameof(CommercialQuoteItem.UnitNetAmount))!.GetScale()); Assert.Equal(5, quote.FindProperty(nameof(CommercialQuote.TaxRatePercent))!.GetPrecision()); Assert.Equal(1000, quote.FindProperty(nameof(CommercialQuote.DetailedDescription))!.GetMaxLength()); Assert.True(quote.FindProperty(nameof(CommercialQuote.CustomerEmail))!.IsNullable);
        var folioProperty = quote.FindProperty(nameof(CommercialQuote.Folio));
        Assert.NotNull(folioProperty); Assert.True(folioProperty.IsNullable); Assert.Equal(40, folioProperty.GetMaxLength());
        Assert.Null(item.FindProperty("Currency")); Assert.Null(quote.FindProperty("PdfPath"));
    }
}
