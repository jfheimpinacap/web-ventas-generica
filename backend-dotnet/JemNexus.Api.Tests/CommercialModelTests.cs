using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialModelTests
{
    private static readonly DbContextOptions<JemNexusDbContext> ContextOptions =
        new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer(
                "Server=(localdb)\\mssqllocaldb;Database=JemNexus_ModelTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;

    [Fact]
    public void DbContextContainsExpectedCommercialDbSets()
    {
        var dbSetProperties = typeof(JemNexusDbContext)
            .GetProperties()
            .Where(property => property.PropertyType.IsGenericType && property.PropertyType.GetGenericTypeDefinition() == typeof(DbSet<>))
            .ToDictionary(property => property.Name, property => property.PropertyType.GetGenericArguments()[0]);

        Assert.Equal(typeof(AppUser), dbSetProperties[nameof(JemNexusDbContext.AppUsers)]);
        Assert.Equal(typeof(AppRefreshToken), dbSetProperties[nameof(JemNexusDbContext.AppRefreshTokens)]);
        Assert.Equal(typeof(Product), dbSetProperties[nameof(JemNexusDbContext.Products)]);
        Assert.Equal(typeof(Category), dbSetProperties[nameof(JemNexusDbContext.Categories)]);
        Assert.Equal(typeof(Brand), dbSetProperties[nameof(JemNexusDbContext.Brands)]);
        Assert.Equal(typeof(Supplier), dbSetProperties[nameof(JemNexusDbContext.Suppliers)]);
        Assert.Equal(typeof(ProductImage), dbSetProperties[nameof(JemNexusDbContext.ProductImages)]);
        Assert.Equal(typeof(ProductSpec), dbSetProperties[nameof(JemNexusDbContext.ProductSpecs)]);
        Assert.Equal(typeof(Promotion), dbSetProperties[nameof(JemNexusDbContext.Promotions)]);
        Assert.Equal(typeof(HomeSectionItem), dbSetProperties[nameof(JemNexusDbContext.HomeSectionItems)]);
        Assert.Equal(typeof(QuoteRequest), dbSetProperties[nameof(JemNexusDbContext.QuoteRequests)]);
    }

    [Fact]
    public void ProductHasRequiredCategoryRelationship()
    {
        using var context = CreateContext();
        var productEntity = context.Model.FindEntityType(typeof(Product));
        Assert.NotNull(productEntity);

        var categoryForeignKey = productEntity.GetForeignKeys()
            .Single(foreignKey => foreignKey.PrincipalEntityType.ClrType == typeof(Category));

        Assert.True(categoryForeignKey.IsRequired);
        Assert.Equal(DeleteBehavior.NoAction, categoryForeignKey.DeleteBehavior);
        Assert.Equal(nameof(Product.CategoryId), categoryForeignKey.Properties.Single().Name);
        Assert.Equal(nameof(Product.Category), categoryForeignKey.DependentToPrincipal?.Name);
        Assert.Equal(nameof(Category.Products), categoryForeignKey.PrincipalToDependent?.Name);
    }

    [Fact]
    public void ProductMachineWeightIsNullableDecimalTwelveTwo()
    {
        using var context = CreateContext();
        var property = context.Model.FindEntityType(typeof(Product))?.FindProperty(nameof(Product.MachineWeightKg));

        Assert.NotNull(property);
        Assert.True(property.IsNullable);
        Assert.Equal("decimal(12,2)", property.GetColumnType());
        Assert.Equal(typeof(decimal?), typeof(Product).GetProperty(nameof(Product.MachineWeightKg))?.PropertyType);
    }


    [Theory]
    [InlineData(typeof(Product), typeof(Category), nameof(Product.CategoryId), nameof(Product.Category), nameof(Category.Products), true)]
    [InlineData(typeof(Product), typeof(Brand), nameof(Product.BrandId), nameof(Product.Brand), nameof(Brand.Products), false)]
    [InlineData(typeof(Product), typeof(Supplier), nameof(Product.SupplierId), nameof(Product.Supplier), nameof(Supplier.Products), false)]
    [InlineData(typeof(ProductImage), typeof(Product), nameof(ProductImage.ProductId), nameof(ProductImage.Product), nameof(Product.Images), true)]
    [InlineData(typeof(ProductSpec), typeof(Product), nameof(ProductSpec.ProductId), nameof(ProductSpec.Product), nameof(Product.Specs), true)]
    [InlineData(typeof(Promotion), typeof(Product), nameof(Promotion.ProductId), nameof(Promotion.Product), nameof(Product.Promotions), false)]
    [InlineData(typeof(HomeSectionItem), typeof(Product), nameof(HomeSectionItem.ProductId), nameof(HomeSectionItem.Product), nameof(Product.HomeSectionItems), true)]
    [InlineData(typeof(Category), typeof(Category), nameof(Category.ParentId), nameof(Category.Parent), nameof(Category.Children), false)]
    public void CommercialRelationshipsUseNoActionDeletes(
        Type dependentType,
        Type principalType,
        string foreignKeyPropertyName,
        string dependentToPrincipalName,
        string principalToDependentName,
        bool isRequired)
    {
        using var context = CreateContext();
        var dependentEntity = context.Model.FindEntityType(dependentType);
        Assert.NotNull(dependentEntity);

        var foreignKey = dependentEntity.GetForeignKeys()
            .Single(foreignKey =>
                foreignKey.PrincipalEntityType.ClrType == principalType
                && foreignKey.Properties.Single().Name == foreignKeyPropertyName);

        Assert.Equal(isRequired, foreignKey.IsRequired);
        Assert.Equal(DeleteBehavior.NoAction, foreignKey.DeleteBehavior);
        Assert.Equal(dependentToPrincipalName, foreignKey.DependentToPrincipal?.Name);
        Assert.Equal(principalToDependentName, foreignKey.PrincipalToDependent?.Name);
    }

    [Theory]
    [InlineData(typeof(QuoteRequest), nameof(QuoteRequest.ProductId), nameof(QuoteRequest.Product), nameof(Product.QuoteRequests))]
    [InlineData(typeof(CommercialQuoteItem), nameof(CommercialQuoteItem.ProductId), nameof(CommercialQuoteItem.Product), null)]
    public void HistoricalProductRelationshipsUseSetNull(
        Type dependentType,
        string foreignKeyPropertyName,
        string dependentToPrincipalName,
        string? principalToDependentName)
    {
        using var context = CreateContext();
        var dependentEntity = context.Model.FindEntityType(dependentType);
        Assert.NotNull(dependentEntity);

        var foreignKey = dependentEntity.GetForeignKeys()
            .Single(foreignKey =>
                foreignKey.PrincipalEntityType.ClrType == typeof(Product)
                && foreignKey.Properties.Single().Name == foreignKeyPropertyName);

        Assert.True(foreignKey.Properties.Single().IsNullable);
        Assert.False(foreignKey.IsRequired);
        Assert.Equal(DeleteBehavior.SetNull, foreignKey.DeleteBehavior);
        Assert.Equal(dependentToPrincipalName, foreignKey.DependentToPrincipal?.Name);
        Assert.Equal(principalToDependentName, foreignKey.PrincipalToDependent?.Name);
    }

    [Fact]
    public void MainCommercialEntitiesAreRegisteredInEfModel()
    {
        using var context = CreateContext();
        var registeredTypes = context.Model.GetEntityTypes()
            .Select(entityType => entityType.ClrType)
            .ToHashSet();

        Assert.Contains(typeof(AppUser), registeredTypes);
        Assert.Contains(typeof(AppRefreshToken), registeredTypes);
        Assert.Contains(typeof(Category), registeredTypes);
        Assert.Contains(typeof(Brand), registeredTypes);
        Assert.Contains(typeof(Supplier), registeredTypes);
        Assert.Contains(typeof(Product), registeredTypes);
        Assert.Contains(typeof(ProductImage), registeredTypes);
        Assert.Contains(typeof(ProductSpec), registeredTypes);
        Assert.Contains(typeof(Promotion), registeredTypes);
        Assert.Contains(typeof(HomeSectionItem), registeredTypes);
        Assert.Contains(typeof(QuoteRequest), registeredTypes);
    }

    [Theory]
    [InlineData(typeof(Category))]
    [InlineData(typeof(Brand))]
    [InlineData(typeof(Supplier))]
    [InlineData(typeof(Product))]
    [InlineData(typeof(ProductImage))]
    [InlineData(typeof(ProductSpec))]
    [InlineData(typeof(Promotion))]
    [InlineData(typeof(HomeSectionItem))]
    [InlineData(typeof(QuoteRequest))]
    public void CommercialAuditForeignKeysPointToAppUser(Type entityType)
    {
        using var context = CreateContext();
        var entity = context.Model.FindEntityType(entityType);
        Assert.NotNull(entity);

        var auditForeignKeys = entity.GetForeignKeys()
            .Where(foreignKey => foreignKey.PrincipalEntityType.ClrType == typeof(AppUser))
            .ToList();

        Assert.Equal(2, auditForeignKeys.Count);
        Assert.Contains(auditForeignKeys, foreignKey => foreignKey.Properties.Single().Name == "CreatedById" && foreignKey.DeleteBehavior == DeleteBehavior.NoAction);
        Assert.Contains(auditForeignKeys, foreignKey => foreignKey.Properties.Single().Name == "UpdatedById" && foreignKey.DeleteBehavior == DeleteBehavior.NoAction);
    }

    private static JemNexusDbContext CreateContext()
    {
        return new JemNexusDbContext(ContextOptions);
    }
}
