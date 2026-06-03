using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialModelTests
{
    [Fact]
    public void DbContextContainsExpectedCommercialDbSets()
    {
        var dbSetProperties = typeof(JemNexusDbContext)
            .GetProperties()
            .Where(property => property.PropertyType.IsGenericType && property.PropertyType.GetGenericTypeDefinition() == typeof(DbSet<>))
            .ToDictionary(property => property.Name, property => property.PropertyType.GetGenericArguments()[0]);

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
        Assert.Equal(DeleteBehavior.Restrict, categoryForeignKey.DeleteBehavior);
        Assert.Equal(nameof(Product.CategoryId), categoryForeignKey.Properties.Single().Name);
        Assert.Equal(nameof(Product.Category), categoryForeignKey.DependentToPrincipal?.Name);
        Assert.Equal(nameof(Category.Products), categoryForeignKey.PrincipalToDependent?.Name);
    }

    [Fact]
    public void MainCommercialEntitiesAreRegisteredInEfModel()
    {
        using var context = CreateContext();
        var registeredTypes = context.Model.GetEntityTypes()
            .Select(entityType => entityType.ClrType)
            .ToHashSet();

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

    private static JemNexusDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\mssqllocaldb;Database=JemNexus_ModelTests;Trusted_Connection=True;TrustServerCertificate=True")
            .Options;

        return new JemNexusDbContext(options);
    }
}
