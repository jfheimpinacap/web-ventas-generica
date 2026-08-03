using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260803000000_AddMachineryTechnicalData")]
public partial class AddMachineryTechnicalData : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<bool>(name: "IncludesCommercialTechnicalAdvice", table: "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.AddColumn<bool>(name: "IncludesCoordinatedDelivery", table: "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.AddColumn<bool>(name: "IncludesTechnicalReview", table: "Products", type: "bit", nullable: false, defaultValue: false);
        migrationBuilder.AddColumn<decimal>(name: "MaximumLoadCapacityKg", table: "Products", type: "decimal(12,2)", nullable: true);
        migrationBuilder.AddColumn<string>(name: "PowerSource", table: "Products", type: "nvarchar(30)", maxLength: 30, nullable: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(name: "IncludesCommercialTechnicalAdvice", table: "Products");
        migrationBuilder.DropColumn(name: "IncludesCoordinatedDelivery", table: "Products");
        migrationBuilder.DropColumn(name: "IncludesTechnicalReview", table: "Products");
        migrationBuilder.DropColumn(name: "MaximumLoadCapacityKg", table: "Products");
        migrationBuilder.DropColumn(name: "PowerSource", table: "Products");
    }
}
