using System.Security.Claims;
using JemNexus.Api.Authorization;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class GranularPermissionTests
{
    [Fact]
    public void CatalogIsUniqueOrderedAndSeparatesReservedPermission()
    {
        Assert.Equal(AppPermissions.All.Length, AppPermissions.All.Distinct(StringComparer.Ordinal).Count());
        Assert.Equal(AppPermissions.All.Order(StringComparer.Ordinal), AppPermissions.All);
        Assert.DoesNotContain(AppPermissions.UsersManage, AppPermissions.SellerGrantable);
        Assert.Equal(
            AppPermissions.UsersManage,
            Assert.Single(AppPermissions.Reserved));
        Assert.All(AppPermissions.SellerGrantable, value => Assert.True(AppPermissions.IsKnown(value)));
        Assert.False(AppPermissions.IsKnown(" products.create"));
        Assert.False(AppPermissions.IsKnown("PRODUCTS.CREATE"));
        Assert.False(AppPermissions.IsKnown("unknown"));
    }

    [Theory]
    [InlineData(AppRoles.SupportAdmin, false, false, null, true)]
    [InlineData(AppRoles.Seller, true, false, "products.create", true)]
    [InlineData(AppRoles.Seller, true, false, null, false)]
    [InlineData("unknown", true, false, "products.create", false)]
    [InlineData("unknown", false, true, "products.create", false)]
    public async Task HandlerFailsClosedAndUsesCurrentDatabaseState(
        string role, bool isStaff, bool isSuperuser, string? persistedPermission, bool expected)
    {
        await using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(nameof(HandlerFailsClosedAndUsesCurrentDatabaseState) + Guid.NewGuid()));
        var user = NewUser(role, isStaff, isSuperuser);
        if (persistedPermission is not null) user.Permissions.Add(new AppUserPermission { Permission = persistedPermission });
        db.Add(user);
        await db.SaveChangesAsync();

        var requirement = new PermissionRequirement(AppPermissions.ProductsCreate);
        var context = Context(user.Id, requirement);
        await new PermissionAuthorizationHandler(db).HandleAsync(context);
        Assert.Equal(expected, context.HasSucceeded);
    }

    [Fact]
    public async Task SellerCannotUseManipulatedReservedOrUnknownRows()
    {
        await using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(nameof(SellerCannotUseManipulatedReservedOrUnknownRows)));
        var seller = NewUser(AppRoles.Seller, true, true);
        seller.Permissions.Add(new AppUserPermission { Permission = AppPermissions.UsersManage });
        seller.Permissions.Add(new AppUserPermission { Permission = "unknown" });
        db.Add(seller);
        await db.SaveChangesAsync();

        foreach (var requested in new[] { AppPermissions.UsersManage, "unknown" })
        {
            var requirement = new PermissionRequirement(requested);
            var context = Context(seller.Id, requirement);
            await new PermissionAuthorizationHandler(db).HandleAsync(context);
            Assert.False(context.HasSucceeded);
        }
        Assert.Empty(await new EffectivePermissionService(db).GetAsync(seller));
    }

    [Fact]
    public async Task RevocationAndInactiveStateApplyOnNextCheck()
    {
        await using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(nameof(RevocationAndInactiveStateApplyOnNextCheck)));
        var seller = NewUser(AppRoles.Seller, true, false);
        seller.Permissions.Add(new AppUserPermission { Permission = AppPermissions.ProductsUpdate });
        db.Add(seller);
        await db.SaveChangesAsync();
        var handler = new PermissionAuthorizationHandler(db);
        var requirement = new PermissionRequirement(AppPermissions.ProductsUpdate);
        var first = Context(seller.Id, requirement);
        await handler.HandleAsync(first);
        Assert.True(first.HasSucceeded);

        db.Remove(seller.Permissions.Single());
        await db.SaveChangesAsync();
        var revoked = Context(seller.Id, requirement);
        await handler.HandleAsync(revoked);
        Assert.False(revoked.HasSucceeded);

        seller.IsActive = false;
        seller.Permissions.Add(new AppUserPermission { Permission = AppPermissions.ProductsUpdate });
        await db.SaveChangesAsync();
        var inactive = Context(seller.Id, requirement);
        await handler.HandleAsync(inactive);
        Assert.False(inactive.HasSucceeded);
    }

    [Fact]
    public void DefaultAssignmentIsCompleteAndIdempotent()
    {
        var seller = NewUser(AppRoles.Seller, true, false);
        DefaultSellerPermissions.EnsureAssigned(seller);
        DefaultSellerPermissions.EnsureAssigned(seller);
        Assert.Equal(AppPermissions.SellerGrantable, seller.Permissions.Select(value => value.Permission).Order(StringComparer.Ordinal));
        Assert.DoesNotContain(seller.Permissions, value => value.Permission == AppPermissions.UsersManage);
    }

    [Fact]
    public void ModelHasCompositeKeyLengthAndCascadeRelationship()
    {
        using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(nameof(ModelHasCompositeKeyLengthAndCascadeRelationship)));
        var entity = db.Model.FindEntityType(typeof(AppUserPermission))!;
        Assert.Equal([nameof(AppUserPermission.UserId), nameof(AppUserPermission.Permission)], entity.FindPrimaryKey()!.Properties.Select(value => value.Name));
        Assert.Equal(AppPermissions.MaxLength, entity.FindProperty(nameof(AppUserPermission.Permission))!.GetMaxLength());
        Assert.Equal(DeleteBehavior.Cascade, entity.GetForeignKeys().Single().DeleteBehavior);
    }

    private static AppUser NewUser(string role, bool isStaff, bool isSuperuser) => new()
    {
        Username = Guid.NewGuid().ToString("N"), PasswordHash = "test", Role = role,
        SellerCode = role == AppRoles.Seller ? Guid.NewGuid().ToString("N")[..12] : null,
        IsActive = true, IsStaff = isStaff, IsSuperuser = isSuperuser
    };

    private static AuthorizationHandlerContext Context(int userId, PermissionRequirement requirement) => new(
        [requirement],
        new ClaimsPrincipal(new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, userId.ToString())], "test")),
        resource: null);
}
