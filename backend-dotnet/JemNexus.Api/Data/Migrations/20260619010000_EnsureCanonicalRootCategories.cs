using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JemNexus.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class EnsureCanonicalRootCategories : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM [Categories]
                    WHERE [ParentId] IS NULL
                      AND ([Slug] = N'maquinaria' OR [Name] = N'Maquinaria' OR [ProductType] = N'machinery')
                )
                BEGIN
                    INSERT INTO [Categories] ([Name], [Slug], [ParentId], [ProductType], [Description], [IsActive], [Order], [CreatedAt], [UpdatedAt], [CreatedById], [UpdatedById])
                    VALUES (N'Maquinaria', N'maquinaria', NULL, N'machinery', N'', CAST(1 AS bit), 1, SYSUTCDATETIME(), SYSUTCDATETIME(), NULL, NULL);
                END;

                IF NOT EXISTS (
                    SELECT 1 FROM [Categories]
                    WHERE [ParentId] IS NULL
                      AND ([Slug] = N'repuestos' OR [Name] = N'Repuestos' OR [ProductType] = N'spare_part')
                )
                BEGIN
                    INSERT INTO [Categories] ([Name], [Slug], [ParentId], [ProductType], [Description], [IsActive], [Order], [CreatedAt], [UpdatedAt], [CreatedById], [UpdatedById])
                    VALUES (N'Repuestos', N'repuestos', NULL, N'spare_part', N'', CAST(1 AS bit), 2, SYSUTCDATETIME(), SYSUTCDATETIME(), NULL, NULL);
                END;

                IF NOT EXISTS (
                    SELECT 1 FROM [Categories]
                    WHERE [ParentId] IS NULL
                      AND ([Slug] = N'servicios' OR [Name] = N'Servicios' OR [ProductType] = N'service')
                )
                BEGIN
                    INSERT INTO [Categories] ([Name], [Slug], [ParentId], [ProductType], [Description], [IsActive], [Order], [CreatedAt], [UpdatedAt], [CreatedById], [UpdatedById])
                    VALUES (N'Servicios', N'servicios', NULL, N'service', N'', CAST(1 AS bit), 3, SYSUTCDATETIME(), SYSUTCDATETIME(), NULL, NULL);
                END;
                """);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
        }
    }
}
