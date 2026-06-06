using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class AuditTimestampTests
{
    [Fact]
    public async Task SaveChangesAsyncSetsCreatedAtAndUpdatedAtForAddedEntities()
    {
        await using var context = CreateInMemoryContext();
        var category = new Category
        {
            Name = "Grúas",
            Slug = "gruas"
        };

        context.Categories.Add(category);
        await context.SaveChangesAsync();

        Assert.NotEqual(default, category.CreatedAt);
        Assert.NotEqual(default, category.UpdatedAt);
        Assert.True(category.UpdatedAt >= category.CreatedAt);
    }

    [Fact]
    public async Task SaveChangesAsyncUpdatesUpdatedAtAndPreservesCreatedAtForModifiedEntities()
    {
        await using var context = CreateInMemoryContext();
        var createdAt = new DateTimeOffset(2026, 1, 15, 12, 0, 0, TimeSpan.Zero);
        var originalUpdatedAt = new DateTimeOffset(2026, 1, 15, 12, 5, 0, TimeSpan.Zero);
        var brand = new Brand
        {
            Name = "Original",
            Slug = "original",
            CreatedAt = createdAt,
            UpdatedAt = originalUpdatedAt
        };

        context.Brands.Add(brand);
        await context.SaveChangesAsync();

        brand.Name = "Actualizada";
        await context.SaveChangesAsync();

        Assert.Equal(createdAt, brand.CreatedAt);
        Assert.True(brand.UpdatedAt > originalUpdatedAt);
    }

    private static JemNexusDbContext CreateInMemoryContext()
    {
        var options = InMemoryTestDatabase.CreateOptions(Guid.NewGuid().ToString());

        return new JemNexusDbContext(options);
    }
}
