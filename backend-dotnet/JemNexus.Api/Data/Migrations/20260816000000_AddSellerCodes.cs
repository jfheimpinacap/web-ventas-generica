using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations;

[DbContext(typeof(JemNexusDbContext))]
[Migration("20260816000000_AddSellerCodes")]
public partial class AddSellerCodes : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateSequence<long>(
            name: "SellerCodeSequence",
            startValue: 1L,
            incrementBy: 1);

        migrationBuilder.AddColumn<string>(
            name: "SellerCode",
            table: "AppUsers",
            type: "nvarchar(24)",
            maxLength: 24,
            nullable: true);

        migrationBuilder.Sql(
            """
            DECLARE @UserId int;
            DECLARE @SequenceValue bigint;
            DECLARE seller_cursor CURSOR LOCAL FAST_FORWARD FOR
                SELECT [Id] FROM [AppUsers] WHERE [Role] = 'seller' ORDER BY [Id];
            OPEN seller_cursor;
            FETCH NEXT FROM seller_cursor INTO @UserId;
            WHILE @@FETCH_STATUS = 0
            BEGIN
                SET @SequenceValue = NEXT VALUE FOR [SellerCodeSequence];
                UPDATE [AppUsers]
                SET [SellerCode] = CONCAT(
                    'VEN-',
                    REPLICATE('0', CASE WHEN LEN(CONVERT(varchar(20), @SequenceValue)) < 4
                        THEN 4 - LEN(CONVERT(varchar(20), @SequenceValue)) ELSE 0 END),
                    CONVERT(varchar(20), @SequenceValue))
                WHERE [Id] = @UserId;
                FETCH NEXT FROM seller_cursor INTO @UserId;
            END;
            CLOSE seller_cursor;
            DEALLOCATE seller_cursor;
            """);

        migrationBuilder.CreateIndex(
            name: "IX_AppUsers_SellerCode",
            table: "AppUsers",
            column: "SellerCode",
            unique: true,
            filter: "[SellerCode] IS NOT NULL");

        migrationBuilder.AddCheckConstraint(
            name: "CK_AppUsers_Role_SellerCode",
            table: "AppUsers",
            sql: "([Role] = 'seller' AND [SellerCode] IS NOT NULL) OR ([Role] <> 'seller' AND [SellerCode] IS NULL)");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropCheckConstraint(name: "CK_AppUsers_Role_SellerCode", table: "AppUsers");
        migrationBuilder.DropIndex(name: "IX_AppUsers_SellerCode", table: "AppUsers");
        migrationBuilder.DropColumn(name: "SellerCode", table: "AppUsers");
        migrationBuilder.DropSequence(name: "SellerCodeSequence");
    }
}
