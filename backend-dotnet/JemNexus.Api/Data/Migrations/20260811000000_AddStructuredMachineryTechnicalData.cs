using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260811000000_AddStructuredMachineryTechnicalData")]
public partial class AddStructuredMachineryTechnicalData : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "TerrainType",
            table: "Products",
            type: "nvarchar(30)",
            maxLength: 30,
            nullable: true);

        migrationBuilder.AddColumn<decimal>(
            name: "WorkingHeightM",
            table: "Products",
            type: "decimal(8,2)",
            nullable: true);

        migrationBuilder.AlterColumn<string>(
            name: "Model",
            table: "Products",
            type: "nvarchar(120)",
            maxLength: 120,
            nullable: true,
            oldClrType: typeof(string),
            oldType: "nvarchar(120)",
            oldMaxLength: 120,
            oldDefaultValue: "");

        migrationBuilder.DropIndex(name: "IX_Products_Sku", table: "Products");
        migrationBuilder.AlterColumn<string>(
            name: "Sku",
            table: "Products",
            type: "nvarchar(120)",
            maxLength: 120,
            nullable: true,
            oldClrType: typeof(string),
            oldType: "nvarchar(120)",
            oldMaxLength: 120,
            oldDefaultValue: "");
        migrationBuilder.Sql("UPDATE [Products] SET [Sku] = NULL WHERE LTRIM(RTRIM([Sku])) = '';");
        migrationBuilder.CreateIndex(
            name: "IX_Products_Sku",
            table: "Products",
            column: "Sku",
            unique: true,
            filter: "[Sku] IS NOT NULL");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropIndex(name: "IX_Products_Sku", table: "Products");
        migrationBuilder.DropColumn(name: "TerrainType", table: "Products");
        migrationBuilder.DropColumn(name: "WorkingHeightM", table: "Products");
        migrationBuilder.Sql("UPDATE [Products] SET [Sku] = '' WHERE [Sku] IS NULL;");
        migrationBuilder.AlterColumn<string>(name: "Sku", table: "Products", type: "nvarchar(120)", maxLength: 120, nullable: false, defaultValue: "", oldClrType: typeof(string), oldType: "nvarchar(120)", oldMaxLength: 120, oldNullable: true);
        migrationBuilder.AlterColumn<string>(name: "Model", table: "Products", type: "nvarchar(120)", maxLength: 120, nullable: false, defaultValue: "", oldClrType: typeof(string), oldType: "nvarchar(120)", oldMaxLength: 120, oldNullable: true);
        migrationBuilder.CreateIndex(name: "IX_Products_Sku", table: "Products", column: "Sku");
    }
}
