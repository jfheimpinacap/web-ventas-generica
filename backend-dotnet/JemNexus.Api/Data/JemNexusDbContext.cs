using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Data;

public sealed class JemNexusDbContext(DbContextOptions<JemNexusDbContext> options) : DbContext(options)
{
    public DbSet<Category> Categories => Set<Category>();
    public DbSet<Brand> Brands => Set<Brand>();
    public DbSet<Supplier> Suppliers => Set<Supplier>();
    public DbSet<Product> Products => Set<Product>();
    public DbSet<ProductImage> ProductImages => Set<ProductImage>();
    public DbSet<ProductSpec> ProductSpecs => Set<ProductSpec>();
    public DbSet<Promotion> Promotions => Set<Promotion>();
    public DbSet<HomeSectionItem> HomeSectionItems => Set<HomeSectionItem>();
    public DbSet<QuoteRequest> QuoteRequests => Set<QuoteRequest>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

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
            entity.HasIndex(category => category.Slug).IsUnique();
            entity.HasIndex(category => category.IsActive);
            entity.HasIndex(category => category.Order);
            entity.HasOne(category => category.Parent)
                .WithMany(category => category.Children)
                .HasForeignKey(category => category.ParentId)
                .OnDelete(DeleteBehavior.SetNull);
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
                .OnDelete(DeleteBehavior.Restrict);
            entity.HasOne(product => product.Brand)
                .WithMany(brand => brand.Products)
                .HasForeignKey(product => product.BrandId)
                .OnDelete(DeleteBehavior.SetNull);
            entity.HasOne(product => product.Supplier)
                .WithMany(supplier => supplier.Products)
                .HasForeignKey(product => product.SupplierId)
                .OnDelete(DeleteBehavior.SetNull);
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
            entity.HasIndex(image => image.IsMain);
            entity.HasIndex(image => new { image.ProductId, image.Order, image.Id });
            entity.HasOne(image => image.Product)
                .WithMany(product => product.Images)
                .HasForeignKey(image => image.ProductId)
                .OnDelete(DeleteBehavior.Cascade);
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
            entity.HasIndex(spec => new { spec.ProductId, spec.Order, spec.Id });
            entity.HasOne(spec => spec.Product)
                .WithMany(product => product.Specs)
                .HasForeignKey(spec => spec.ProductId)
                .OnDelete(DeleteBehavior.Cascade);
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
            entity.HasIndex(promotion => promotion.IsActive);
            entity.HasIndex(promotion => promotion.Order);
            entity.HasIndex(promotion => promotion.StartsAt);
            entity.HasIndex(promotion => promotion.EndsAt);
            entity.HasOne(promotion => promotion.Product)
                .WithMany(product => product.Promotions)
                .HasForeignKey(promotion => promotion.ProductId)
                .OnDelete(DeleteBehavior.SetNull);
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
            entity.HasIndex(item => item.IsActive);
            entity.HasIndex(item => new { item.Section, item.Position }).IsUnique();
            entity.HasIndex(item => new { item.Section, item.ProductId }).IsUnique();
            entity.HasOne(item => item.Product)
                .WithMany(product => product.HomeSectionItems)
                .HasForeignKey(item => item.ProductId)
                .OnDelete(DeleteBehavior.Cascade);
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
            entity.HasIndex(quote => quote.Status);
            entity.HasIndex(quote => quote.CreatedAt);
            entity.HasOne(quote => quote.Product)
                .WithMany(product => product.QuoteRequests)
                .HasForeignKey(quote => quote.ProductId)
                .OnDelete(DeleteBehavior.SetNull);
        });
    }
}
