using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

public partial class AddProductTechnicalSheetAssociation : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<int>(name: "TechnicalSheetId", table: "Products", type: "int", nullable: true);
        migrationBuilder.CreateIndex(name: "IX_Products_TechnicalSheetId", table: "Products", column: "TechnicalSheetId");
        migrationBuilder.AddForeignKey(
            name: "FK_Products_TechnicalSheets_TechnicalSheetId",
            table: "Products",
            column: "TechnicalSheetId",
            principalTable: "TechnicalSheets",
            principalColumn: "Id",
            onDelete: ReferentialAction.SetNull);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropForeignKey(name: "FK_Products_TechnicalSheets_TechnicalSheetId", table: "Products");
        migrationBuilder.DropIndex(name: "IX_Products_TechnicalSheetId", table: "Products");
        migrationBuilder.DropColumn(name: "TechnicalSheetId", table: "Products");
    }
}
