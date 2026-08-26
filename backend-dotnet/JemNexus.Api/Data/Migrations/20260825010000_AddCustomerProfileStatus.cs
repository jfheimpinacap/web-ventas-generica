using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260825010000_AddCustomerProfileStatus")]
public partial class AddCustomerProfileStatus : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder) =>
        migrationBuilder.AddColumn<bool>(
            name: "IsActive",
            table: "CustomerProfiles",
            type: "bit",
            nullable: false,
            defaultValue: true);

    protected override void Down(MigrationBuilder migrationBuilder) =>
        migrationBuilder.DropColumn(
            name: "IsActive",
            table: "CustomerProfiles");
}
