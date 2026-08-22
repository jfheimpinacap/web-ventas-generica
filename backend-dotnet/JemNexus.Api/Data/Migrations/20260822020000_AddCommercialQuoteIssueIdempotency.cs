using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260822020000_AddCommercialQuoteIssueIdempotency")]
public partial class AddCommercialQuoteIssueIdempotency : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "CommercialQuoteIssueIdempotencyRecords",
            columns: table => new
            {
                ResponsibleSellerId = table.Column<int>(type: "int", nullable: false),
                IdempotencyKey = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                RequestFingerprint = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                CommercialQuoteId = table.Column<int>(type: "int", nullable: false),
                CreatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_CommercialQuoteIssueIdempotencyRecords", x => new { x.ResponsibleSellerId, x.IdempotencyKey });
                table.ForeignKey("FK_CommercialQuoteIssueIdempotencyRecords_AppUsers_ResponsibleSellerId", x => x.ResponsibleSellerId, "AppUsers", "Id", onDelete: ReferentialAction.NoAction);
                table.ForeignKey("FK_CommercialQuoteIssueIdempotencyRecords_CommercialQuotes_CommercialQuoteId", x => x.CommercialQuoteId, "CommercialQuotes", "Id", onDelete: ReferentialAction.Cascade);
            });
        migrationBuilder.CreateIndex("UX_CommercialQuoteIssueIdempotencyRecords_CommercialQuoteId", "CommercialQuoteIssueIdempotencyRecords", "CommercialQuoteId", unique: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder) => migrationBuilder.DropTable("CommercialQuoteIssueIdempotencyRecords");
}
