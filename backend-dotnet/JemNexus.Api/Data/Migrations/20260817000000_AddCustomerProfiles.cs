using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260817000000_AddCustomerProfiles")]
public partial class AddCustomerProfiles : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "CustomerProfiles",
            columns: table => new
            {
                Id = table.Column<int>(type: "int", nullable: false).Annotation("SqlServer:Identity", "1, 1"),
                BusinessName = table.Column<string>(type: "nvarchar(200)", maxLength: 200, nullable: false),
                Rut = table.Column<string>(type: "nvarchar(12)", maxLength: 12, nullable: false),
                NormalizedRut = table.Column<string>(type: "nvarchar(12)", maxLength: 12, nullable: false),
                BusinessActivity = table.Column<string>(type: "nvarchar(200)", maxLength: 200, nullable: false),
                Address = table.Column<string>(type: "nvarchar(300)", maxLength: 300, nullable: false),
                Phone = table.Column<string>(type: "nvarchar(30)", maxLength: 30, nullable: false),
                CityOrCommune = table.Column<string>(type: "nvarchar(120)", maxLength: 120, nullable: false),
                ContactName = table.Column<string>(type: "nvarchar(200)", maxLength: 200, nullable: false),
                Email = table.Column<string>(type: "nvarchar(254)", maxLength: 254, nullable: true),
                NormalizedBusinessName = table.Column<string>(type: "nvarchar(200)", maxLength: 200, nullable: false),
                CreatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()"),
                UpdatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
                ,CreatedById = table.Column<int>(type: "int", nullable: true)
                ,UpdatedById = table.Column<int>(type: "int", nullable: true)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_CustomerProfiles", x => x.Id);
                table.ForeignKey("FK_CustomerProfiles_AppUsers_CreatedById", x => x.CreatedById, "AppUsers", "Id", onDelete: ReferentialAction.NoAction);
                table.ForeignKey("FK_CustomerProfiles_AppUsers_UpdatedById", x => x.UpdatedById, "AppUsers", "Id", onDelete: ReferentialAction.NoAction);
            });
        migrationBuilder.CreateIndex(name: "IX_CustomerProfiles_CreatedById", table: "CustomerProfiles", column: "CreatedById");
        migrationBuilder.CreateIndex(name: "IX_CustomerProfiles_UpdatedById", table: "CustomerProfiles", column: "UpdatedById");
        migrationBuilder.CreateIndex(name: "IX_CustomerProfiles_NormalizedBusinessName", table: "CustomerProfiles", column: "NormalizedBusinessName");
        migrationBuilder.CreateIndex(name: "IX_CustomerProfiles_NormalizedRut", table: "CustomerProfiles", column: "NormalizedRut", unique: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder) => migrationBuilder.DropTable(name: "CustomerProfiles");
}
