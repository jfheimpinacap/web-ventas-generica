using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable
namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20261020000000_AddMachineryRental")]
public partial class AddMachineryRental : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>("CommercialMode", "Products", type: "nvarchar(20)", maxLength: 20, nullable: false, defaultValue: "sale");
        migrationBuilder.AddColumn<decimal>("PlatformHeightM", "Products", type: "decimal(8,2)", nullable: true);
        migrationBuilder.AddColumn<decimal>("RentalPriceDay", "Products", type: "decimal(12,0)", nullable: true);
        migrationBuilder.AddColumn<decimal>("RentalPriceWeek", "Products", type: "decimal(12,0)", nullable: true);
        migrationBuilder.AddColumn<decimal>("RentalPriceMonth", "Products", type: "decimal(12,0)", nullable: true);
        migrationBuilder.AddColumn<bool>("RentalIncludesTechnicalAdvice", "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.AddColumn<bool>("RentalIncludesOnsiteService", "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.AddColumn<bool>("RentalIncludesTransportCoordination", "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.CreateIndex("IX_Products_CommercialMode_ProductType", "Products", new[] { "CommercialMode", "ProductType" });
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropIndex("IX_Products_CommercialMode_ProductType", "Products");
        migrationBuilder.DropColumn("CommercialMode", "Products");
        migrationBuilder.DropColumn("PlatformHeightM", "Products");
        migrationBuilder.DropColumn("RentalPriceDay", "Products");
        migrationBuilder.DropColumn("RentalPriceWeek", "Products");
        migrationBuilder.DropColumn("RentalPriceMonth", "Products");
        migrationBuilder.DropColumn("RentalIncludesTechnicalAdvice", "Products");
        migrationBuilder.DropColumn("RentalIncludesOnsiteService", "Products");
        migrationBuilder.DropColumn("RentalIncludesTransportCoordination", "Products");
    }
}
