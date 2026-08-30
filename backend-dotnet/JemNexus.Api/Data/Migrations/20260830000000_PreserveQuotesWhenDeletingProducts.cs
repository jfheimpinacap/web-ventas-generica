using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260830000000_PreserveQuotesWhenDeletingProducts")]
public partial class PreserveQuotesWhenDeletingProducts : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        ReplaceProductForeignKey(migrationBuilder, "CommercialQuoteItems", ReferentialAction.SetNull);
        ReplaceProductForeignKey(migrationBuilder, "QuoteRequests", ReferentialAction.SetNull);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        ReplaceProductForeignKey(migrationBuilder, "CommercialQuoteItems", ReferentialAction.NoAction);
        ReplaceProductForeignKey(migrationBuilder, "QuoteRequests", ReferentialAction.NoAction);
    }

    private static void ReplaceProductForeignKey(MigrationBuilder migrationBuilder, string table, ReferentialAction deleteBehavior)
    {
        var foreignKey = $"FK_{table}_Products_ProductId";
        migrationBuilder.DropForeignKey(name: foreignKey, table: table);
        migrationBuilder.AddForeignKey(
            name: foreignKey,
            table: table,
            column: "ProductId",
            principalTable: "Products",
            principalColumn: "Id",
            onDelete: deleteBehavior);
    }
}
