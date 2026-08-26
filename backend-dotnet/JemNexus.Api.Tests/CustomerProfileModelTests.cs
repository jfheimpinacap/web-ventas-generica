using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CustomerProfileModelTests
{
    [Fact]
    public void ModelHasSafeLengthsAndUniqueNormalizedRut()
    {
        using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions("customers-model"));
        var entity = db.Model.FindEntityType(typeof(CustomerProfile))!;
        Assert.True(entity.GetIndexes().Single(index => index.Properties.Single().Name == nameof(CustomerProfile.NormalizedRut)).IsUnique);
        Assert.Contains(entity.GetIndexes(), index => index.Properties.Single().Name == nameof(CustomerProfile.NormalizedBusinessName));
        Assert.Equal(254, entity.FindProperty(nameof(CustomerProfile.Email))!.GetMaxLength());
        Assert.True(entity.FindProperty(nameof(CustomerProfile.Email))!.IsNullable);
        var active = entity.FindProperty(nameof(CustomerProfile.IsActive))!;
        Assert.Equal(typeof(bool), active.ClrType);
        Assert.False(active.IsNullable);
        Assert.Equal(true, active.GetDefaultValue());
        Assert.DoesNotContain(entity.GetIndexes(), index => index.Properties.Count == 1 && index.Properties[0].Name == nameof(CustomerProfile.IsActive));
    }
}
