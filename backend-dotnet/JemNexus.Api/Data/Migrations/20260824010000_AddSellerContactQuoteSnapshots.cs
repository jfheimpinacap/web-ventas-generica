using JemNexus.Api.Data;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260824010000_AddSellerContactQuoteSnapshots")]
public partial class AddSellerContactQuoteSnapshots : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>("Phone", "AppUsers", "nvarchar(32)", maxLength: 32, nullable: true);
        migrationBuilder.AddColumn<string>("ResponsibleSellerEmail", "CommercialQuotes", "nvarchar(254)", maxLength: 254, nullable: true);
        migrationBuilder.AddColumn<string>("ResponsibleSellerPhone", "CommercialQuotes", "nvarchar(32)", maxLength: 32, nullable: true);

        migrationBuilder.Sql("""
            UPDATE [AppUsers]
            SET [Phone] = N'+56 9 4611 5064'
            WHERE [Email] = N'jmateluna@jem-nexus.cl'
              AND ([Phone] IS NULL OR LTRIM(RTRIM([Phone])) = N'');

            UPDATE q
            SET q.[ResponsibleSellerEmail] = u.[Email],
                q.[ResponsibleSellerPhone] = u.[Phone]
            FROM [CommercialQuotes] AS q
            INNER JOIN [AppUsers] AS u ON u.[Id] = q.[ResponsibleSellerId];
            """);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn("ResponsibleSellerPhone", "CommercialQuotes");
        migrationBuilder.DropColumn("ResponsibleSellerEmail", "CommercialQuotes");
        migrationBuilder.DropColumn("Phone", "AppUsers");
    }
}
