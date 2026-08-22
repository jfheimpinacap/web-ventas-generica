using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260822000000_AddRefreshTokenRotation")]
public partial class AddRefreshTokenRotation : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<Guid>(
            name: "FamilyId",
            table: "AppRefreshTokens",
            type: "uniqueidentifier",
            nullable: false,
            defaultValueSql: "NEWID()");

        migrationBuilder.AddColumn<string>(
            name: "ReplacedByTokenHash",
            table: "AppRefreshTokens",
            type: "nvarchar(128)",
            maxLength: 128,
            nullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_AppRefreshTokens_FamilyId",
            table: "AppRefreshTokens",
            column: "FamilyId");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropIndex(name: "IX_AppRefreshTokens_FamilyId", table: "AppRefreshTokens");
        migrationBuilder.DropColumn(name: "ReplacedByTokenHash", table: "AppRefreshTokens");
        migrationBuilder.DropColumn(name: "FamilyId", table: "AppRefreshTokens");
    }
}
