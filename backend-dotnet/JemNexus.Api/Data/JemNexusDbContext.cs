using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JemNexus.Api.Data;

public sealed class JemNexusDbContext(DbContextOptions<JemNexusDbContext> options) : DbContext(options)
{
    public DbSet<AppUser> AppUsers => Set<AppUser>();
    public DbSet<AppRefreshToken> AppRefreshTokens => Set<AppRefreshToken>();
    public DbSet<Category> Categories => Set<Category>();
    public DbSet<Brand> Brands => Set<Brand>();
    public DbSet<Supplier> Suppliers => Set<Supplier>();
    public DbSet<Product> Products => Set<Product>();
    public DbSet<ProductImage> ProductImages => Set<ProductImage>();
    public DbSet<ProductSpec> ProductSpecs => Set<ProductSpec>();
    public DbSet<Promotion> Promotions => Set<Promotion>();
    public DbSet<HomeSectionItem> HomeSectionItems => Set<HomeSectionItem>();
    public DbSet<QuoteRequest> QuoteRequests => Set<QuoteRequest>();

    public override int SaveChanges()
    {
        ApplyAuditTimestamps();
        return base.SaveChanges();
    }

    public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
    {
        ApplyAuditTimestamps();
        return base.SaveChangesAsync(cancellationToken);
    }

    private void ApplyAuditTimestamps()
    {
        var utcNow = DateTimeOffset.UtcNow;

        foreach (var entry in ChangeTracker.Entries().Where(entry => IsTimestampAuditedEntity(entry.Entity)))
        {
            if (entry.State == EntityState.Added)
            {
                var createdAtProperty = entry.Property("CreatedAt");
                if (createdAtProperty.CurrentValue is DateTimeOffset createdAt && createdAt == default)
                {
                    createdAtProperty.CurrentValue = utcNow;
                }

                entry.Property("UpdatedAt").CurrentValue = utcNow;
            }
            else if (entry.State == EntityState.Modified)
            {
                entry.Property("CreatedAt").IsModified = false;
                entry.Property("UpdatedAt").CurrentValue = utcNow;
            }
        }
    }

    private static bool IsTimestampAuditedEntity(object entity)
    {
        return entity is AppUser
            or AppRefreshToken
            or Category
            or Brand
            or Supplier
            or Product
            or ProductImage
            or ProductSpec
            or Promotion
            or HomeSectionItem
            or QuoteRequest;
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        ConfigureAppUser(modelBuilder);
        ConfigureAppRefreshToken(modelBuilder);
        ConfigureCategory(modelBuilder);
        ConfigureBrand(modelBuilder);
        ConfigureSupplier(modelBuilder);
        ConfigureProduct(modelBuilder);
        ConfigureProductImage(modelBuilder);
        ConfigureProductSpec(modelBuilder);
        ConfigurePromotion(modelBuilder);
        ConfigureHomeSectionItem(modelBuilder);
        ConfigureQuoteRequest(modelBuilder);
    }


    private static void ConfigureAppUser(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AppUser>(entity =>
        {
            entity.ToTable("AppUsers");
            entity.HasKey(user => user.Id);
            entity.Property(user => user.Username).HasMaxLength(150).IsRequired();
            entity.Property(user => user.Email).HasMaxLength(254);
            entity.Property(user => user.PasswordHash).HasMaxLength(500).IsRequired();
            entity.Property(user => user.Role).HasMaxLength(40).IsRequired();
            entity.Property(user => user.FullName).HasMaxLength(180);
            entity.Property(user => user.IsActive).HasDefaultValue(true);
            entity.Property(user => user.IsStaff).HasDefaultValue(false);
            entity.Property(user => user.IsSuperuser).HasDefaultValue(false);
            entity.Property(user => user.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(user => user.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.HasIndex(user => user.Username).IsUnique();
            entity.HasIndex(user => user.Email).IsUnique().HasFilter("[Email] IS NOT NULL");
            entity.HasIndex(user => user.Role);
            entity.HasIndex(user => user.IsActive);
        });
    }

    private static void ConfigureAppRefreshToken(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AppRefreshToken>(entity =>
        {
            entity.ToTable("AppRefreshTokens");
            entity.HasKey(token => token.Id);
            entity.Property(token => token.TokenHash).HasMaxLength(128).IsRequired();
            entity.Property(token => token.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(token => token.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.HasIndex(token => token.TokenHash).IsUnique();
            entity.HasIndex(token => new { token.UserId, token.ExpiresAt });
            entity.HasOne(token => token.User)
                .WithMany(user => user.RefreshTokens)
                .HasForeignKey(token => token.UserId)
                .OnDelete(DeleteBehavior.Cascade);
        });
    }

    private static void ConfigureAuditUsers<TEntity>(EntityTypeBuilder<TEntity> entity)
        where TEntity : class
    {
        entity.HasOne(typeof(AppUser), "CreatedBy")
            .WithMany()
            .HasForeignKey("CreatedById")
            .OnDelete(DeleteBehavior.NoAction);
        entity.HasOne(typeof(AppUser), "UpdatedBy")
            .WithMany()
            .HasForeignKey("UpdatedById")
            .OnDelete(DeleteBehavior.NoAction);
    }

    private static void ConfigureCategory(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Category>(entity =>
        {
            entity.ToTable("Categories");
            entity.HasKey(category => category.Id);
            entity.Property(category => category.Name).HasMaxLength(120).IsRequired();
            entity.Property(category => category.Slug).HasMaxLength(140).IsRequired();
            entity.Property(category => category.Description).HasDefaultValue(string.Empty);
            entity.Property(category => category.IsActive).HasDefaultValue(true);
            entity.Property(category => category.Order).HasDefaultValue(0);
            entity.Property(category => category.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(category => category.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(category => category.Slug).IsUnique();
            entity.HasIndex(category => category.IsActive);
            entity.HasIndex(category => category.Order);
            entity.HasOne(category => category.Parent)
                .WithMany(category => category.Children)
                .HasForeignKey(category => category.ParentId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigureBrand(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Brand>(entity =>
        {
            entity.ToTable("Brands");
            entity.HasKey(brand => brand.Id);
            entity.Property(brand => brand.Name).HasMaxLength(120).IsRequired();
            entity.Property(brand => brand.Slug).HasMaxLength(140).IsRequired();
            entity.Property(brand => brand.Logo).HasMaxLength(500);
            entity.Property(brand => brand.Description).HasDefaultValue(string.Empty);
            entity.Property(brand => brand.IsActive).HasDefaultValue(true);
            entity.Property(brand => brand.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(brand => brand.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(brand => brand.Slug).IsUnique();
            entity.HasIndex(brand => brand.IsActive);
            entity.HasIndex(brand => brand.Name);
        });
    }

    private static void ConfigureSupplier(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Supplier>(entity =>
        {
            entity.ToTable("Suppliers");
            entity.HasKey(supplier => supplier.Id);
            entity.Property(supplier => supplier.Name).HasMaxLength(160).IsRequired();
            entity.Property(supplier => supplier.ContactName).HasMaxLength(160).HasDefaultValue(string.Empty);
            entity.Property(supplier => supplier.Phone).HasMaxLength(40).HasDefaultValue(string.Empty);
            entity.Property(supplier => supplier.Email).HasMaxLength(254).HasDefaultValue(string.Empty);
            entity.Property(supplier => supplier.Notes).HasDefaultValue(string.Empty);
            entity.Property(supplier => supplier.IsActive).HasDefaultValue(true);
            entity.Property(supplier => supplier.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(supplier => supplier.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(supplier => supplier.IsActive);
            entity.HasIndex(supplier => supplier.Name);
        });
    }

    private static void ConfigureProduct(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Product>(entity =>
        {
            entity.ToTable("Products");
            entity.HasKey(product => product.Id);
            entity.Property(product => product.Name).HasMaxLength(220).IsRequired();
            entity.Property(product => product.Slug).HasMaxLength(240).IsRequired();
            entity.Property(product => product.ProductType).HasMaxLength(20).HasDefaultValue(ProductTypes.Machinery).IsRequired();
            entity.Property(product => product.Condition).HasMaxLength(20).HasDefaultValue(ProductConditions.NotApplicable).IsRequired();
            entity.Property(product => product.ShortDescription).HasMaxLength(280).HasDefaultValue(string.Empty);
            entity.Property(product => product.Description).HasDefaultValue(string.Empty);
            entity.Property(product => product.Model).HasMaxLength(120).HasDefaultValue(string.Empty);
            entity.Property(product => product.Sku).HasMaxLength(120).HasDefaultValue(string.Empty);
            entity.Property(product => product.Price).HasColumnType("decimal(12,2)");
            entity.Property(product => product.PriceVisible).HasDefaultValue(true);
            entity.Property(product => product.StockStatus).HasMaxLength(20).HasDefaultValue(StockStatuses.OnRequest).IsRequired();
            entity.Property(product => product.IsFeatured).HasDefaultValue(false);
            entity.Property(product => product.IsPublished).HasDefaultValue(true);
            entity.Property(product => product.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(product => product.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(product => product.Slug).IsUnique();
            entity.HasIndex(product => product.Sku);
            entity.HasIndex(product => product.ProductType);
            entity.HasIndex(product => product.Condition);
            entity.HasIndex(product => product.StockStatus);
            entity.HasIndex(product => product.IsFeatured);
            entity.HasIndex(product => product.IsPublished);
            entity.HasOne(product => product.Category)
                .WithMany(category => category.Products)
                .HasForeignKey(product => product.CategoryId)
                .OnDelete(DeleteBehavior.NoAction);
            entity.HasOne(product => product.Brand)
                .WithMany(brand => brand.Products)
                .HasForeignKey(product => product.BrandId)
                .OnDelete(DeleteBehavior.NoAction);
            entity.HasOne(product => product.Supplier)
                .WithMany(supplier => supplier.Products)
                .HasForeignKey(product => product.SupplierId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigureProductImage(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<ProductImage>(entity =>
        {
            entity.ToTable("ProductImages");
            entity.HasKey(image => image.Id);
            entity.Property(image => image.Image).HasMaxLength(500).IsRequired();
            entity.Property(image => image.AltText).HasMaxLength(220).HasDefaultValue(string.Empty);
            entity.Property(image => image.IsMain).HasDefaultValue(false);
            entity.Property(image => image.Order).HasDefaultValue(0);
            entity.Property(image => image.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(image => image.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(image => image.IsMain);
            entity.HasIndex(image => new { image.ProductId, image.Order, image.Id });
            entity.HasOne(image => image.Product)
                .WithMany(product => product.Images)
                .HasForeignKey(image => image.ProductId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigureProductSpec(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<ProductSpec>(entity =>
        {
            entity.ToTable("ProductSpecs");
            entity.HasKey(spec => spec.Id);
            entity.Property(spec => spec.Key).HasMaxLength(120).IsRequired();
            entity.Property(spec => spec.Value).HasMaxLength(220).IsRequired();
            entity.Property(spec => spec.Unit).HasMaxLength(40).HasDefaultValue(string.Empty);
            entity.Property(spec => spec.Order).HasDefaultValue(0);
            entity.Property(spec => spec.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(spec => spec.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(spec => new { spec.ProductId, spec.Order, spec.Id });
            entity.HasOne(spec => spec.Product)
                .WithMany(product => product.Specs)
                .HasForeignKey(spec => spec.ProductId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigurePromotion(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Promotion>(entity =>
        {
            entity.ToTable("Promotions");
            entity.HasKey(promotion => promotion.Id);
            entity.Property(promotion => promotion.Title).HasMaxLength(180).IsRequired();
            entity.Property(promotion => promotion.Subtitle).HasMaxLength(280).HasDefaultValue(string.Empty);
            entity.Property(promotion => promotion.Image).HasMaxLength(500);
            entity.Property(promotion => promotion.ButtonText).HasMaxLength(80).HasDefaultValue(string.Empty);
            entity.Property(promotion => promotion.ButtonUrl).HasMaxLength(2048).HasDefaultValue(string.Empty);
            entity.Property(promotion => promotion.IsActive).HasDefaultValue(true);
            entity.Property(promotion => promotion.Order).HasDefaultValue(0);
            entity.Property(promotion => promotion.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(promotion => promotion.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(promotion => promotion.IsActive);
            entity.HasIndex(promotion => promotion.Order);
            entity.HasIndex(promotion => promotion.StartsAt);
            entity.HasIndex(promotion => promotion.EndsAt);
            entity.HasOne(promotion => promotion.Product)
                .WithMany(product => product.Promotions)
                .HasForeignKey(promotion => promotion.ProductId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigureHomeSectionItem(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<HomeSectionItem>(entity =>
        {
            entity.ToTable("HomeSectionItems");
            entity.HasKey(item => item.Id);
            entity.Property(item => item.Section).HasMaxLength(40).IsRequired();
            entity.Property(item => item.Position).HasDefaultValue(1);
            entity.Property(item => item.IsActive).HasDefaultValue(true);
            entity.Property(item => item.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(item => item.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(item => item.IsActive);
            entity.HasIndex(item => new { item.Section, item.Position }).IsUnique();
            entity.HasIndex(item => new { item.Section, item.ProductId }).IsUnique();
            entity.HasOne(item => item.Product)
                .WithMany(product => product.HomeSectionItems)
                .HasForeignKey(item => item.ProductId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }

    private static void ConfigureQuoteRequest(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<QuoteRequest>(entity =>
        {
            entity.ToTable("QuoteRequests");
            entity.HasKey(quote => quote.Id);
            entity.Property(quote => quote.CustomerName).HasMaxLength(160).IsRequired();
            entity.Property(quote => quote.CustomerPhone).HasMaxLength(40).IsRequired();
            entity.Property(quote => quote.CustomerEmail).HasMaxLength(254).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.CompanyName).HasMaxLength(160).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.City).HasMaxLength(120).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.PreferredContactMethod).HasMaxLength(20).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.Message).IsRequired();
            entity.Property(quote => quote.Status).HasMaxLength(20).HasDefaultValue(QuoteStatuses.New).IsRequired();
            entity.Property(quote => quote.InternalNotes).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.SellerResponse).HasDefaultValue(string.Empty);
            entity.Property(quote => quote.CreatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            entity.Property(quote => quote.UpdatedAt).HasDefaultValueSql("SYSUTCDATETIME()");
            ConfigureAuditUsers(entity);
            entity.HasIndex(quote => quote.Status);
            entity.HasIndex(quote => quote.CreatedAt);
            entity.HasOne(quote => quote.Product)
                .WithMany(product => product.QuoteRequests)
                .HasForeignKey(quote => quote.ProductId)
                .OnDelete(DeleteBehavior.NoAction);
        });
    }
}
