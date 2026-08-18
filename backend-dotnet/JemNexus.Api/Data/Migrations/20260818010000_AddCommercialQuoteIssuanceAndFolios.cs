using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260818010000_AddCommercialQuoteIssuanceAndFolios")]
public partial class AddCommercialQuoteIssuanceAndFolios : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>("Folio", "CommercialQuotes", "nvarchar(40)", maxLength: 40, nullable: true);
        migrationBuilder.AddColumn<int>("FolioYear", "CommercialQuotes", "int", nullable: true);
        migrationBuilder.AddColumn<long>("FolioSequenceNumber", "CommercialQuotes", "bigint", nullable: true);
        migrationBuilder.AddColumn<DateTime>("IssuedAtUtc", "CommercialQuotes", "datetime2", nullable: true);
        migrationBuilder.AddColumn<DateOnly>("IssuedOn", "CommercialQuotes", "date", nullable: true);
        migrationBuilder.CreateTable("CommercialQuoteFolioCounters", table => new
        {
            Year = table.Column<int>("int", nullable: false),
            LastNumber = table.Column<long>("bigint", nullable: false)
        }, constraints: table => table.PrimaryKey("PK_CommercialQuoteFolioCounters", value => value.Year));
        migrationBuilder.CreateIndex("UX_CommercialQuotes_Folio", "CommercialQuotes", "Folio", unique: true, filter: "[Folio] IS NOT NULL");
        migrationBuilder.CreateIndex("UX_CommercialQuotes_FolioYear_Sequence", "CommercialQuotes", new[] { "FolioYear", "FolioSequenceNumber" }, unique: true, filter: "[FolioYear] IS NOT NULL AND [FolioSequenceNumber] IS NOT NULL");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable("CommercialQuoteFolioCounters");
        migrationBuilder.DropIndex("UX_CommercialQuotes_Folio", "CommercialQuotes");
        migrationBuilder.DropIndex("UX_CommercialQuotes_FolioYear_Sequence", "CommercialQuotes");
        migrationBuilder.DropColumn("Folio", "CommercialQuotes");
        migrationBuilder.DropColumn("FolioYear", "CommercialQuotes");
        migrationBuilder.DropColumn("FolioSequenceNumber", "CommercialQuotes");
        migrationBuilder.DropColumn("IssuedAtUtc", "CommercialQuotes");
        migrationBuilder.DropColumn("IssuedOn", "CommercialQuotes");
    }
}
