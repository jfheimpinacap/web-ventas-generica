using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260817010000_AddCommercialQuotes")]
public partial class AddCommercialQuotes : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable("CommercialQuotes", table => new
        {
            Id = table.Column<int>("int", nullable: false).Annotation("SqlServer:Identity", "1, 1"), Status = table.Column<string>("nvarchar(20)", maxLength: 20, nullable: false, defaultValue: "Draft"), Currency = table.Column<string>("nvarchar(3)", maxLength: 3, nullable: false), SaleCondition = table.Column<string>("nvarchar(20)", maxLength: 20, nullable: false), ValidityDays = table.Column<int>("int", nullable: false, defaultValue: 15), DetailedDescription = table.Column<string>("nvarchar(1000)", maxLength: 1000, nullable: true), TaxRatePercent = table.Column<decimal>("decimal(5,2)", nullable: false, defaultValue: 19.00m), CustomerProfileId = table.Column<int>("int", nullable: true), CustomerBusinessName = table.Column<string>("nvarchar(200)", maxLength: 200, nullable: false), CustomerRut = table.Column<string>("nvarchar(12)", maxLength: 12, nullable: false), CustomerBusinessActivity = table.Column<string>("nvarchar(200)", maxLength: 200, nullable: false), CustomerAddress = table.Column<string>("nvarchar(300)", maxLength: 300, nullable: false), CustomerPhone = table.Column<string>("nvarchar(30)", maxLength: 30, nullable: false), CustomerCityOrCommune = table.Column<string>("nvarchar(120)", maxLength: 120, nullable: false), CustomerContactName = table.Column<string>("nvarchar(200)", maxLength: 200, nullable: false), CustomerEmail = table.Column<string>("nvarchar(254)", maxLength: 254, nullable: true), ResponsibleSellerId = table.Column<int>("int", nullable: false), ResponsibleSellerName = table.Column<string>("nvarchar(180)", maxLength: 180, nullable: false), ResponsibleSellerCode = table.Column<string>("nvarchar(24)", maxLength: 24, nullable: false), NetAmount = table.Column<decimal>("decimal(18,2)", nullable: false), TaxAmount = table.Column<decimal>("decimal(18,2)", nullable: false), TotalAmount = table.Column<decimal>("decimal(18,2)", nullable: false), CreatedAt = table.Column<DateTimeOffset>("datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()"), UpdatedAt = table.Column<DateTimeOffset>("datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
        }, constraints: table => { table.PrimaryKey("PK_CommercialQuotes", x => x.Id); table.ForeignKey("FK_CommercialQuotes_CustomerProfiles_CustomerProfileId", x => x.CustomerProfileId, "CustomerProfiles", "Id", onDelete: ReferentialAction.SetNull); table.ForeignKey("FK_CommercialQuotes_AppUsers_ResponsibleSellerId", x => x.ResponsibleSellerId, "AppUsers", "Id", onDelete: ReferentialAction.NoAction); });
        migrationBuilder.CreateTable("CommercialQuoteItems", table => new
        {
            Id = table.Column<int>("int", nullable: false).Annotation("SqlServer:Identity", "1, 1"), CommercialQuoteId = table.Column<int>("int", nullable: false), Position = table.Column<int>("int", nullable: false), Origin = table.Column<string>("nvarchar(20)", maxLength: 20, nullable: false), ProductId = table.Column<int>("int", nullable: true), ProductName = table.Column<string>("nvarchar(220)", maxLength: 220, nullable: false), BrandName = table.Column<string>("nvarchar(120)", maxLength: 120, nullable: true), ModelName = table.Column<string>("nvarchar(120)", maxLength: 120, nullable: true), Quantity = table.Column<int>("int", nullable: false), UnitNetAmount = table.Column<decimal>("decimal(18,2)", nullable: false), DiscountPercent = table.Column<decimal>("decimal(5,2)", nullable: false), FinalUnitNetAmount = table.Column<decimal>("decimal(18,2)", nullable: false), LineNetAmount = table.Column<decimal>("decimal(18,2)", nullable: false)
        }, constraints: table => { table.PrimaryKey("PK_CommercialQuoteItems", x => x.Id); table.ForeignKey("FK_CommercialQuoteItems_CommercialQuotes_CommercialQuoteId", x => x.CommercialQuoteId, "CommercialQuotes", "Id", onDelete: ReferentialAction.Cascade); table.ForeignKey("FK_CommercialQuoteItems_Products_ProductId", x => x.ProductId, "Products", "Id", onDelete: ReferentialAction.NoAction); });
        migrationBuilder.CreateIndex("IX_CommercialQuotes_Status", "CommercialQuotes", "Status"); migrationBuilder.CreateIndex("IX_CommercialQuotes_ResponsibleSellerId", "CommercialQuotes", "ResponsibleSellerId"); migrationBuilder.CreateIndex("IX_CommercialQuotes_CustomerProfileId", "CommercialQuotes", "CustomerProfileId"); migrationBuilder.CreateIndex("IX_CommercialQuotes_CreatedAt", "CommercialQuotes", "CreatedAt");
        migrationBuilder.CreateIndex("IX_CommercialQuoteItems_CommercialQuoteId_Position", "CommercialQuoteItems", new[] { "CommercialQuoteId", "Position" }, unique: true); migrationBuilder.CreateIndex("IX_CommercialQuoteItems_ProductId", "CommercialQuoteItems", "ProductId");
    }

    protected override void Down(MigrationBuilder migrationBuilder) { migrationBuilder.DropTable("CommercialQuoteItems"); migrationBuilder.DropTable("CommercialQuotes"); }
}
