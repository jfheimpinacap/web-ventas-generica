using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddAuthUsersAndAuditRelations : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "AppUsers",
                columns: table => new
                {
                    Id = table.Column<int>(type: "int", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    Username = table.Column<string>(type: "nvarchar(150)", maxLength: 150, nullable: false),
                    Email = table.Column<string>(type: "nvarchar(254)", maxLength: 254, nullable: true),
                    PasswordHash = table.Column<string>(type: "nvarchar(500)", maxLength: 500, nullable: false),
                    Role = table.Column<string>(type: "nvarchar(40)", maxLength: 40, nullable: false),
                    FullName = table.Column<string>(type: "nvarchar(180)", maxLength: 180, nullable: true),
                    IsActive = table.Column<bool>(type: "bit", nullable: false, defaultValue: true),
                    IsStaff = table.Column<bool>(type: "bit", nullable: false, defaultValue: false),
                    IsSuperuser = table.Column<bool>(type: "bit", nullable: false, defaultValue: false),
                    LastLoginAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: true),
                    CreatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()"),
                    UpdatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AppUsers", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "AppRefreshTokens",
                columns: table => new
                {
                    Id = table.Column<int>(type: "int", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    UserId = table.Column<int>(type: "int", nullable: false),
                    TokenHash = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    ExpiresAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    RevokedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: true),
                    CreatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()"),
                    UpdatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AppRefreshTokens", x => x.Id);
                    table.ForeignKey(
                        name: "FK_AppRefreshTokens_AppUsers_UserId",
                        column: x => x.UserId,
                        principalTable: "AppUsers",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Suppliers_CreatedById",
                table: "Suppliers",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Suppliers_UpdatedById",
                table: "Suppliers",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_QuoteRequests_CreatedById",
                table: "QuoteRequests",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_QuoteRequests_UpdatedById",
                table: "QuoteRequests",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Promotions_CreatedById",
                table: "Promotions",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Promotions_UpdatedById",
                table: "Promotions",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_ProductSpecs_CreatedById",
                table: "ProductSpecs",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_ProductSpecs_UpdatedById",
                table: "ProductSpecs",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Products_CreatedById",
                table: "Products",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Products_UpdatedById",
                table: "Products",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_ProductImages_CreatedById",
                table: "ProductImages",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_ProductImages_UpdatedById",
                table: "ProductImages",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_HomeSectionItems_CreatedById",
                table: "HomeSectionItems",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_HomeSectionItems_UpdatedById",
                table: "HomeSectionItems",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Categories_CreatedById",
                table: "Categories",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Categories_UpdatedById",
                table: "Categories",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Brands_CreatedById",
                table: "Brands",
                column: "CreatedById");

            migrationBuilder.CreateIndex(
                name: "IX_Brands_UpdatedById",
                table: "Brands",
                column: "UpdatedById");

            migrationBuilder.CreateIndex(
                name: "IX_AppRefreshTokens_TokenHash",
                table: "AppRefreshTokens",
                column: "TokenHash",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_AppRefreshTokens_UserId_ExpiresAt",
                table: "AppRefreshTokens",
                columns: new[] { "UserId", "ExpiresAt" });

            migrationBuilder.CreateIndex(
                name: "IX_AppUsers_Email",
                table: "AppUsers",
                column: "Email",
                unique: true,
                filter: "[Email] IS NOT NULL");

            migrationBuilder.CreateIndex(
                name: "IX_AppUsers_IsActive",
                table: "AppUsers",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_AppUsers_Role",
                table: "AppUsers",
                column: "Role");

            migrationBuilder.CreateIndex(
                name: "IX_AppUsers_Username",
                table: "AppUsers",
                column: "Username",
                unique: true);

            migrationBuilder.AddForeignKey(
                name: "FK_Brands_AppUsers_CreatedById",
                table: "Brands",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Brands_AppUsers_UpdatedById",
                table: "Brands",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Categories_AppUsers_CreatedById",
                table: "Categories",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Categories_AppUsers_UpdatedById",
                table: "Categories",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_HomeSectionItems_AppUsers_CreatedById",
                table: "HomeSectionItems",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_HomeSectionItems_AppUsers_UpdatedById",
                table: "HomeSectionItems",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_ProductImages_AppUsers_CreatedById",
                table: "ProductImages",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_ProductImages_AppUsers_UpdatedById",
                table: "ProductImages",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Products_AppUsers_CreatedById",
                table: "Products",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Products_AppUsers_UpdatedById",
                table: "Products",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_ProductSpecs_AppUsers_CreatedById",
                table: "ProductSpecs",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_ProductSpecs_AppUsers_UpdatedById",
                table: "ProductSpecs",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Promotions_AppUsers_CreatedById",
                table: "Promotions",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Promotions_AppUsers_UpdatedById",
                table: "Promotions",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_QuoteRequests_AppUsers_CreatedById",
                table: "QuoteRequests",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_QuoteRequests_AppUsers_UpdatedById",
                table: "QuoteRequests",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Suppliers_AppUsers_CreatedById",
                table: "Suppliers",
                column: "CreatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Suppliers_AppUsers_UpdatedById",
                table: "Suppliers",
                column: "UpdatedById",
                principalTable: "AppUsers",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Brands_AppUsers_CreatedById",
                table: "Brands");

            migrationBuilder.DropForeignKey(
                name: "FK_Brands_AppUsers_UpdatedById",
                table: "Brands");

            migrationBuilder.DropForeignKey(
                name: "FK_Categories_AppUsers_CreatedById",
                table: "Categories");

            migrationBuilder.DropForeignKey(
                name: "FK_Categories_AppUsers_UpdatedById",
                table: "Categories");

            migrationBuilder.DropForeignKey(
                name: "FK_HomeSectionItems_AppUsers_CreatedById",
                table: "HomeSectionItems");

            migrationBuilder.DropForeignKey(
                name: "FK_HomeSectionItems_AppUsers_UpdatedById",
                table: "HomeSectionItems");

            migrationBuilder.DropForeignKey(
                name: "FK_ProductImages_AppUsers_CreatedById",
                table: "ProductImages");

            migrationBuilder.DropForeignKey(
                name: "FK_ProductImages_AppUsers_UpdatedById",
                table: "ProductImages");

            migrationBuilder.DropForeignKey(
                name: "FK_Products_AppUsers_CreatedById",
                table: "Products");

            migrationBuilder.DropForeignKey(
                name: "FK_Products_AppUsers_UpdatedById",
                table: "Products");

            migrationBuilder.DropForeignKey(
                name: "FK_ProductSpecs_AppUsers_CreatedById",
                table: "ProductSpecs");

            migrationBuilder.DropForeignKey(
                name: "FK_ProductSpecs_AppUsers_UpdatedById",
                table: "ProductSpecs");

            migrationBuilder.DropForeignKey(
                name: "FK_Promotions_AppUsers_CreatedById",
                table: "Promotions");

            migrationBuilder.DropForeignKey(
                name: "FK_Promotions_AppUsers_UpdatedById",
                table: "Promotions");

            migrationBuilder.DropForeignKey(
                name: "FK_QuoteRequests_AppUsers_CreatedById",
                table: "QuoteRequests");

            migrationBuilder.DropForeignKey(
                name: "FK_QuoteRequests_AppUsers_UpdatedById",
                table: "QuoteRequests");

            migrationBuilder.DropForeignKey(
                name: "FK_Suppliers_AppUsers_CreatedById",
                table: "Suppliers");

            migrationBuilder.DropForeignKey(
                name: "FK_Suppliers_AppUsers_UpdatedById",
                table: "Suppliers");

            migrationBuilder.DropTable(
                name: "AppRefreshTokens");

            migrationBuilder.DropTable(
                name: "AppUsers");

            migrationBuilder.DropIndex(
                name: "IX_Suppliers_CreatedById",
                table: "Suppliers");

            migrationBuilder.DropIndex(
                name: "IX_Suppliers_UpdatedById",
                table: "Suppliers");

            migrationBuilder.DropIndex(
                name: "IX_QuoteRequests_CreatedById",
                table: "QuoteRequests");

            migrationBuilder.DropIndex(
                name: "IX_QuoteRequests_UpdatedById",
                table: "QuoteRequests");

            migrationBuilder.DropIndex(
                name: "IX_Promotions_CreatedById",
                table: "Promotions");

            migrationBuilder.DropIndex(
                name: "IX_Promotions_UpdatedById",
                table: "Promotions");

            migrationBuilder.DropIndex(
                name: "IX_ProductSpecs_CreatedById",
                table: "ProductSpecs");

            migrationBuilder.DropIndex(
                name: "IX_ProductSpecs_UpdatedById",
                table: "ProductSpecs");

            migrationBuilder.DropIndex(
                name: "IX_Products_CreatedById",
                table: "Products");

            migrationBuilder.DropIndex(
                name: "IX_Products_UpdatedById",
                table: "Products");

            migrationBuilder.DropIndex(
                name: "IX_ProductImages_CreatedById",
                table: "ProductImages");

            migrationBuilder.DropIndex(
                name: "IX_ProductImages_UpdatedById",
                table: "ProductImages");

            migrationBuilder.DropIndex(
                name: "IX_HomeSectionItems_CreatedById",
                table: "HomeSectionItems");

            migrationBuilder.DropIndex(
                name: "IX_HomeSectionItems_UpdatedById",
                table: "HomeSectionItems");

            migrationBuilder.DropIndex(
                name: "IX_Categories_CreatedById",
                table: "Categories");

            migrationBuilder.DropIndex(
                name: "IX_Categories_UpdatedById",
                table: "Categories");

            migrationBuilder.DropIndex(
                name: "IX_Brands_CreatedById",
                table: "Brands");

            migrationBuilder.DropIndex(
                name: "IX_Brands_UpdatedById",
                table: "Brands");
        }
    }
}
