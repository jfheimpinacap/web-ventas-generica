using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260922000000_AddCommercialQuoteIssuedBy")]
public sealed class AddCommercialQuoteIssuedBy : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<int>(
            name: "IssuedById",
            table: "CommercialQuotes",
            type: "int",
            nullable: true);

        migrationBuilder.Sql("UPDATE [CommercialQuotes] SET [IssuedById] = [ResponsibleSellerId] WHERE [IssuedById] IS NULL;");

        migrationBuilder.AlterColumn<int>(
            name: "IssuedById",
            table: "CommercialQuotes",
            type: "int",
            nullable: false,
            oldClrType: typeof(int),
            oldType: "int",
            oldNullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_CommercialQuotes_IssuedById",
            table: "CommercialQuotes",
            column: "IssuedById");

        migrationBuilder.AddForeignKey(
            name: "FK_CommercialQuotes_AppUsers_IssuedById",
            table: "CommercialQuotes",
            column: "IssuedById",
            principalTable: "AppUsers",
            principalColumn: "Id",
            onDelete: ReferentialAction.NoAction);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropForeignKey(
            name: "FK_CommercialQuotes_AppUsers_IssuedById",
            table: "CommercialQuotes");

        migrationBuilder.DropIndex(
            name: "IX_CommercialQuotes_IssuedById",
            table: "CommercialQuotes");

        migrationBuilder.DropColumn(
            name: "IssuedById",
            table: "CommercialQuotes");
    }
}
