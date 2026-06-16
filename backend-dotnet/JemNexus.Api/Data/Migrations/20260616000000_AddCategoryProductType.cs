using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddCategoryProductType : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "ProductType",
                table: "Categories",
                type: "nvarchar(20)",
                maxLength: 20,
                nullable: false,
                defaultValue: "machinery");

            migrationBuilder.CreateIndex(
                name: "IX_Categories_ProductType",
                table: "Categories",
                column: "ProductType");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_Categories_ProductType",
                table: "Categories");

            migrationBuilder.DropColumn(
                name: "ProductType",
                table: "Categories");
        }
    }
}
