using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260917000000_AddGranularSellerPermissions")]
public partial class AddGranularSellerPermissions : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "AppUserPermissions",
            columns: table => new
            {
                UserId = table.Column<int>(type: "int", nullable: false),
                Permission = table.Column<string>(type: "nvarchar(80)", maxLength: 80, nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_AppUserPermissions", value => new { value.UserId, value.Permission });
                table.ForeignKey("FK_AppUserPermissions_AppUsers_UserId", value => value.UserId, "AppUsers", "Id", onDelete: ReferentialAction.Cascade);
            });

        foreach (var permission in AppPermissions.SellerGrantable)
        {
            var escaped = permission.Replace("'", "''", StringComparison.Ordinal);
            migrationBuilder.Sql($$"""
                INSERT INTO [AppUserPermissions] ([UserId], [Permission])
                SELECT [Id], N'{{escaped}}' FROM [AppUsers]
                WHERE [Role] = N'seller'
                  AND NOT EXISTS (
                    SELECT 1 FROM [AppUserPermissions] p
                    WHERE p.[UserId] = [AppUsers].[Id] AND p.[Permission] = N'{{escaped}}');
                """);
        }
    }

    protected override void Down(MigrationBuilder migrationBuilder) =>
        migrationBuilder.DropTable(name: "AppUserPermissions");
}
