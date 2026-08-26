using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Globalization;
using System.Text.Json;
using System.Xml.Linq;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Services.TechnicalSheets;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class CommercialPublicReadEndpointTests : IDisposable
{
    private readonly MemoryTechnicalSheetStorage _storage = new();
    private readonly CommercialWriteEndpointTests.CommercialWriteApiFactory _factory;

    public CommercialPublicReadEndpointTests()
    {
        _factory = new(services =>
        {
            services.RemoveAll<ITechnicalSheetStorage>();
            services.AddSingleton<ITechnicalSheetStorage>(_storage);
        });
    }

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task PublicProductSitemapIsAnonymousXmlAndUsesConfiguredCanonicalHost()
    {
        await SeedPublicCatalogDataAsync();
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            db.Products.AddRange(
                new Product { Id = 7, Name = "Sin Marca", Slug = "sin-marca", CategoryId = 1, Brand = null, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true },
                new Product { Id = 8, Name = "Slug Especial", Slug = "seguro /?#", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true },
                new Product { Id = 9, Name = "Slug Repetido", Slug = "sin-marca", CategoryId = 1, Brand = null, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.OnRequest, IsPublished = true },
                new Product { Id = 10, Name = "Slug Vacío", Slug = "   ", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true });
            await db.SaveChangesAsync();
        }
        using var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Host = "attacker.example";

        using var response = await client.GetAsync("/api/public/sitemap-products.xml");
        var body = await response.Content.ReadAsStringAsync();
        var document = XDocument.Parse(body);
        XNamespace sitemapNamespace = "http://www.sitemaps.org/schemas/sitemap/0.9";
        var locations = document.Root!.Elements(sitemapNamespace + "url")
            .Select(element => element.Element(sitemapNamespace + "loc")!.Value)
            .ToList();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("application/xml", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal("utf-8", response.Content.Headers.ContentType?.CharSet);
        Assert.Equal(sitemapNamespace, document.Root.Name.Namespace);
        Assert.Contains("https://jem-nexus.cl/producto/excavadora", locations);
        Assert.Contains("https://jem-nexus.cl/producto/sin-marca", locations);
        Assert.Contains("https://jem-nexus.cl/producto/seguro%20%2F%3F%23", locations);
        Assert.Equal(locations.Count, locations.Distinct(StringComparer.Ordinal).Count());
        Assert.Equal(locations.Order(StringComparer.Ordinal), locations);
        Assert.All(locations, location =>
        {
            var uri = new Uri(location);
            Assert.Equal(Uri.UriSchemeHttps, uri.Scheme);
            Assert.Equal("jem-nexus.cl", uri.Host);
            Assert.Empty(uri.Query);
            Assert.Empty(uri.Fragment);
        });
        Assert.DoesNotContain(locations, location => location.Contains("attacker.example", StringComparison.Ordinal));
        Assert.DoesNotContain(locations, location => location.Contains("api.jem-nexus.cl", StringComparison.Ordinal));
        Assert.Equal("public, max-age=3600", response.Headers.CacheControl?.ToString());
        Assert.DoesNotContain("/admin", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("supplier", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("customer", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicProductSitemapAppliesPublicFiltersAndUsesProductUpdatedAt()
    {
        await SeedPublicCatalogDataAsync();
        DateTimeOffset persistedUpdatedAt;
        using (var scope = _factory.Services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            persistedUpdatedAt = await dbContext.Products
                .AsNoTracking()
                .Where(product => product.Slug == "excavadora")
                .Select(product => product.UpdatedAt)
                .SingleAsync();
        }

        var expectedLastModified = persistedUpdatedAt
            .ToUniversalTime()
            .ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);
        using var client = _factory.CreateClient();

        var document = XDocument.Parse(await (await client.GetAsync("/api/public/sitemap-products.xml")).Content.ReadAsStringAsync());
        var body = document.ToString();
        XNamespace sitemapNamespace = "http://www.sitemaps.org/schemas/sitemap/0.9";
        var excavator = document.Root!.Elements(sitemapNamespace + "url")
            .Single(element => element.Element(sitemapNamespace + "loc")!.Value.EndsWith("/producto/excavadora", StringComparison.Ordinal));

        Assert.Equal(expectedLastModified, excavator.Element(sitemapNamespace + "lastmod")!.Value);
        Assert.DoesNotContain("borrador", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("excavadora-vendida", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("producto-inactivo", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("marca-oculta", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicProductSitemapCanReturnAnEmptyUrlset()
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync("/api/public/sitemap-products.xml");
        var document = XDocument.Parse(await response.Content.ReadAsStringAsync());
        XNamespace sitemapNamespace = "http://www.sitemaps.org/schemas/sitemap/0.9";

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Empty(document.Root!.Elements(sitemapNamespace + "url"));
    }

    [Theory]
    [InlineData("/api/public/products/")]
    [InlineData("/api/public/categories/")]
    [InlineData("/api/public/brands/")]
    [InlineData("/api/public/promotions/")]
    [InlineData("/api/public/home-section-items/")]
    public async Task PublicReadEndpointsAllowAnonymous(string path)
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task PublicProductsFilterUnpublishedAndInactiveRelationsAndExcludeAdminFields()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var products = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?include_unpublished=true"));
        var body = products.ToString();

        Assert.Single(products.EnumerateArray());
        Assert.Equal("excavadora", products[0].GetProperty("slug").GetString());
        Assert.DoesNotContain("borrador", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("categoria-inactiva", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("created_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("updated_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("created_by", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("updated_by", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("supplier", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("password", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicProductListExposesNullableTechnicalDataWithoutSku()
    {
        await SeedPublicCatalogDataAsync();
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var product = await db.Products.SingleAsync(candidate => candidate.Slug == "excavadora");
            product.Model = "GS-1930";
            product.WorkingHeightM = 7.79m;
            product.MaximumLoadCapacityKg = 227m;
            product.PowerSource = ProductPowerSources.Electric24V;
            product.TerrainType = ProductTerrainTypes.IndoorSmooth;
            product.Year = 2021;
            product.Sku = "PRIVATE-SKU";
            await db.SaveChangesAsync();
        }
        using var client = _factory.CreateClient();

        var products = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?search=excavadora"));
        var productPayload = Assert.Single(products.EnumerateArray());

        Assert.Equal("excavadora", productPayload.GetProperty("slug").GetString());
        Assert.Equal("GS-1930", productPayload.GetProperty("model").GetString());
        Assert.Equal(7.79m, productPayload.GetProperty("working_height_m").GetDecimal());
        Assert.Equal(227m, productPayload.GetProperty("maximum_load_capacity_kg").GetDecimal());
        Assert.Equal(ProductPowerSources.Electric24V, productPayload.GetProperty("power_source").GetString());
        Assert.Equal(ProductTerrainTypes.IndoorSmooth, productPayload.GetProperty("terrain_type").GetString());
        Assert.Equal(2021, productPayload.GetProperty("year").GetInt32());
        Assert.False(productPayload.TryGetProperty("sku", out _));

        var homeItems = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/home-section-items/"));
        var homeProduct = homeItems.EnumerateArray()
            .Select(item => item.GetProperty("product"))
            .Single(product => product.GetProperty("slug").GetString() == "excavadora");
        AssertTechnicalData(homeProduct);

        var promotions = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/promotions/"));
        var promotionProduct = promotions.EnumerateArray()
            .Where(promotion => promotion.GetProperty("product").ValueKind == JsonValueKind.Object)
            .Select(promotion => promotion.GetProperty("product"))
            .Single(product => product.GetProperty("slug").GetString() == "excavadora");
        AssertTechnicalData(promotionProduct);

        var detail = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/excavadora/"));
        Assert.Equal("GS-1930", detail.GetProperty("model").GetString());
        Assert.Equal(7.79m, detail.GetProperty("working_height_m").GetDecimal());
        Assert.Equal(ProductTerrainTypes.IndoorSmooth, detail.GetProperty("terrain_type").GetString());
        Assert.Equal(2021, detail.GetProperty("year").GetInt32());
    }

    [Fact]
    public async Task PublicProductListSerializesMissingTechnicalDataAsNull()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var products = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/"));
        var productPayload = Assert.Single(products.EnumerateArray());

        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("model").ValueKind);
        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("working_height_m").ValueKind);
        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("maximum_load_capacity_kg").ValueKind);
        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("power_source").ValueKind);
        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("terrain_type").ValueKind);
        Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("year").ValueKind);
    }

    [Fact]
    public async Task PublicProductListSerializesEveryProductTypeWithoutTechnicalData()
    {
        await SeedPublicCatalogDataAsync();
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            db.Products.AddRange(
                new Product { Id = 20, Name = "Maquinaria nueva", Slug = "technical-new", CategoryId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.New, StockStatus = StockStatuses.Available, IsPublished = true },
                new Product { Id = 21, Name = "Repuesto", Slug = "technical-spare", CategoryId = 1, ProductType = ProductTypes.SparePart, Condition = ProductConditions.NotApplicable, StockStatus = StockStatuses.Available, IsPublished = true },
                new Product { Id = 22, Name = "Servicio", Slug = "technical-service", CategoryId = 1, ProductType = ProductTypes.Service, Condition = ProductConditions.NotApplicable, StockStatus = StockStatuses.Available, IsPublished = true });
            await db.SaveChangesAsync();
        }
        using var client = _factory.CreateClient();

        foreach (var slug in new[] { "excavadora", "technical-new", "technical-spare", "technical-service" })
        {
            var products = await ReadJsonAsync<JsonElement>(await client.GetAsync($"/api/public/products/?search={slug}"));
            var productPayload = Assert.Single(products.EnumerateArray());
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("model").ValueKind);
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("working_height_m").ValueKind);
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("maximum_load_capacity_kg").ValueKind);
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("power_source").ValueKind);
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("terrain_type").ValueKind);
            Assert.Equal(JsonValueKind.Null, productPayload.GetProperty("year").ValueKind);
        }
    }

    [Fact]
    public async Task PublicProductDetailReturnsPublishedProductAndHidesUnpublishedProduct()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var published = await client.GetAsync("/api/public/products/excavadora/");
        var unpublished = await client.GetAsync("/api/public/products/borrador/");
        var inactiveCategory = await client.GetAsync("/api/public/products/producto-inactivo/");
        var inactiveBrand = await client.GetAsync("/api/public/products/marca-oculta/");
        var payload = await ReadJsonAsync<JsonElement>(published);
        var body = payload.ToString();

        Assert.Equal(HttpStatusCode.OK, published.StatusCode);
        Assert.Equal("excavadora", payload.GetProperty("slug").GetString());
        Assert.Equal(HttpStatusCode.NotFound, unpublished.StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, inactiveCategory.StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, inactiveBrand.StatusCode);
        Assert.DoesNotContain("created_at", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("supplier", body, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task PublicTechnicalSheetMetadataAndFileAreSafeAndProductBound()
    {
        await SeedPublicCatalogDataAsync();
        var bytes = new byte[] { 0x25, 0x50, 0x44, 0x46, 1, 2, 3, 4 };
        _storage.Files["sheet.pdf"] = bytes;
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var product = await db.Products.SingleAsync(candidate => candidate.Id == 1);
            product.TechnicalSheet = CreateTechnicalSheet("sheet.pdf", "manual.pdf", "application/pdf", bytes.Length);
            await db.SaveChangesAsync();
        }
        using var client = _factory.CreateClient();

        var detailResponse = await client.GetAsync("/api/public/products/excavadora/");
        var detail = await ReadJsonAsync<JsonElement>(detailResponse);
        var sheet = detail.GetProperty("technical_sheet");
        Assert.Equal("/public/products/excavadora/technical-sheet/file", sheet.GetProperty("file_url").GetString());
        Assert.Equal("manual.pdf", sheet.GetProperty("original_file_name").GetString());
        Assert.DoesNotContain("storage", detail.ToString(), StringComparison.OrdinalIgnoreCase);

        var inline = await client.GetAsync("/api/public/products/excavadora/technical-sheet/file");
        Assert.Equal(HttpStatusCode.OK, inline.StatusCode);
        Assert.Equal("application/pdf", inline.Content.Headers.ContentType?.MediaType);
        Assert.Equal(bytes, await inline.Content.ReadAsByteArrayAsync());
        Assert.False(inline.Content.Headers.ContentDisposition?.DispositionType == "attachment");
        Assert.Equal("nosniff", inline.Headers.GetValues("X-Content-Type-Options").Single());
        Assert.Equal("noindex, nofollow, noarchive", inline.Headers.GetValues("X-Robots-Tag").Single());
        Assert.Equal("no-store", inline.Headers.CacheControl?.ToString());

        var explicitInline = await client.GetAsync("/api/public/products/excavadora/technical-sheet/file?download=false");
        Assert.Equal(HttpStatusCode.OK, explicitInline.StatusCode);
        Assert.False(explicitInline.Content.Headers.ContentDisposition?.DispositionType == "attachment");

        var download = await client.GetAsync("/api/public/products/1/technical-sheet/file?download=true");
        Assert.Equal(HttpStatusCode.OK, download.StatusCode);
        Assert.Equal("attachment", download.Content.Headers.ContentDisposition?.DispositionType);
        Assert.Equal("manual.pdf", download.Content.Headers.ContentDisposition?.FileNameStar);
    }

    [Fact]
    public async Task ProductWithoutTechnicalSheetReturnsNullMetadataAndNotFoundFile()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();
        var detail = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/excavadora/"));
        Assert.Equal(JsonValueKind.Null, detail.GetProperty("technical_sheet").ValueKind);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/public/products/excavadora/technical-sheet/file")).StatusCode);
    }

    [Fact]
    public async Task PublicTechnicalSheetMetadataContainsOnlyTheSafeContract()
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync("sheet.pdf", "manual.pdf", "application/pdf", [1, 2, 3, 4]);
        using var client = _factory.CreateClient();

        var detail = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/excavadora/"));
        var sheet = detail.GetProperty("technical_sheet");
        var propertyNames = sheet.EnumerateObject().Select(property => property.Name).OrderBy(name => name).ToArray();
        Assert.Equal(new[] { "content_type", "created_at", "file_url", "id", "name", "original_file_name", "size_bytes", "updated_at" }, propertyNames);
        Assert.Equal("Manual público", sheet.GetProperty("name").GetString());
        Assert.Equal("application/pdf", sheet.GetProperty("content_type").GetString());
        Assert.Equal(4, sheet.GetProperty("size_bytes").GetInt64());
        Assert.Equal(JsonValueKind.String, sheet.GetProperty("created_at").ValueKind);
        Assert.Equal(JsonValueKind.String, sheet.GetProperty("updated_at").ValueKind);
        AssertSafePublicPayload(detail.ToString());
    }

    [Fact]
    public async Task PublicListsHomeAndPromotionsDoNotExposeTechnicalSheet()
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync("sheet.pdf", "manual.pdf", "application/pdf", [1]);
        using var client = _factory.CreateClient();

        foreach (var path in new[] { "/api/public/products/", "/api/public/home-section-items/", "/api/public/promotions/" })
        {
            using var response = await client.GetAsync(path);
            var body = await response.Content.ReadAsStringAsync();
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.DoesNotContain("technical_sheet", body, StringComparison.OrdinalIgnoreCase);
            AssertSafePublicPayload(body);
        }
    }

    [Theory]
    [InlineData("sheet.pdf", "manual.pdf", "application/pdf")]
    [InlineData("sheet.jpg", "manual.jpg", "image/jpeg")]
    [InlineData("sheet.png", "manual.png", "image/png")]
    [InlineData("sheet.webp", "manual.webp", "image/webp")]
    public async Task PublicTechnicalSheetServesEveryAllowedFormatWithExactBytes(string storageKey, string originalFileName, string contentType)
    {
        await SeedPublicCatalogDataAsync();
        var bytes = new byte[] { 0, 1, 2, 3, 4, 255 };
        await AttachTechnicalSheetAsync(storageKey, originalFileName, contentType, bytes);
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync("/api/public/products/excavadora/technical-sheet/file");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(contentType, response.Content.Headers.ContentType?.MediaType);
        Assert.Equal(bytes, await response.Content.ReadAsByteArrayAsync());
    }

    [Fact]
    public async Task PublicTechnicalSheetSupportsSeekableRangeRequests()
    {
        await SeedPublicCatalogDataAsync();
        var bytes = new byte[] { 10, 20, 30, 40, 50, 60 };
        await AttachTechnicalSheetAsync("sheet.pdf", "manual.pdf", "application/pdf", bytes);
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/public/products/excavadora/technical-sheet/file");
        request.Headers.Range = new RangeHeaderValue(1, 3);

        using var response = await client.SendAsync(request);

        Assert.Equal(HttpStatusCode.PartialContent, response.StatusCode);
        Assert.Equal("bytes 1-3/6", response.Content.Headers.ContentRange?.ToString());
        Assert.Equal(new byte[] { 20, 30, 40 }, await response.Content.ReadAsByteArrayAsync());
        Assert.True(_storage.LastOpenedStreamWasSeekable);
    }

    [Fact]
    public async Task MissingTechnicalSheetFileReturnsSafeNotFound()
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync("missing.pdf", "manual.pdf", "application/pdf", [1]);
        using var client = _factory.CreateClient();

        await AssertSafeNotFoundAsync(client, "/api/public/products/excavadora/technical-sheet/file");
    }

    [Theory]
    [InlineData("../secret.pdf", "manual.pdf", "application/pdf")]
    [InlineData("folder/secret.pdf", "manual.pdf", "application/pdf")]
    [InlineData("folder\\secret.pdf", "manual.pdf", "application/pdf")]
    [InlineData("invalid.pdf", "manual.pdf", "application/pdf")]
    public async Task InvalidOrTraversalStorageKeyReturnsSafeNotFound(string storageKey, string originalFileName, string contentType)
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync(storageKey, originalFileName, contentType, [1]);
        _storage.InvalidKeys.Add(storageKey);
        using var client = _factory.CreateClient();

        await AssertSafeNotFoundAsync(client, "/api/public/products/excavadora/technical-sheet/file");
    }

    [Theory]
    [InlineData("manual.svg", "image/svg+xml")]
    [InlineData("manual.gif", "image/gif")]
    [InlineData("manual.pdf", "application/octet-stream")]
    [InlineData("manual.pdf", "image/png")]
    [InlineData("manual.png", "application/pdf")]
    public async Task UnsupportedOrMismatchedTechnicalSheetFormatReturnsSafeNotFound(string originalFileName, string contentType)
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync("sheet.bin", originalFileName, contentType, [1]);
        using var client = _factory.CreateClient();

        await AssertSafeNotFoundAsync(client, "/api/public/products/excavadora/technical-sheet/file");
    }

    [Theory]
    [InlineData("no-existe")]
    [InlineData("borrador")]
    [InlineData("excavadora-vendida")]
    [InlineData("producto-inactivo")]
    [InlineData("marca-oculta")]
    public async Task NonPublicProductsReturnIndistinguishableSafeNotFoundForTechnicalSheet(string slug)
    {
        await SeedPublicCatalogDataAsync();
        await AttachTechnicalSheetAsync("sheet.pdf", "manual.pdf", "application/pdf", [1], 3, 4, 5, 6);
        using var client = _factory.CreateClient();

        await AssertSafeNotFoundAsync(client, $"/api/public/products/{slug}/technical-sheet/file");
    }

    [Fact]
    public async Task SharedTechnicalSheetIsServedThroughEachPublicProduct()
    {
        await SeedPublicCatalogDataAsync();
        var bytes = new byte[] { 7, 8, 9 };
        _storage.Files["shared.pdf"] = bytes;
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            var first = await db.Products.SingleAsync(product => product.Id == 1);
            var second = new Product { Id = 7, Name = "Segunda pública", Slug = "segunda-publica", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };
            var sheet = CreateTechnicalSheet("shared.pdf", "shared.pdf", "application/pdf", bytes.Length);
            first.TechnicalSheet = sheet;
            second.TechnicalSheet = sheet;
            db.Products.Add(second);
            await db.SaveChangesAsync();
        }
        using var client = _factory.CreateClient();

        using var firstResponse = await client.GetAsync("/api/public/products/excavadora/technical-sheet/file");
        using var secondResponse = await client.GetAsync("/api/public/products/segunda-publica/technical-sheet/file");
        Assert.Equal(HttpStatusCode.OK, firstResponse.StatusCode);
        Assert.Equal(HttpStatusCode.OK, secondResponse.StatusCode);
        Assert.Equal("application/pdf", firstResponse.Content.Headers.ContentType?.MediaType);
        Assert.Equal("application/pdf", secondResponse.Content.Headers.ContentType?.MediaType);
        Assert.Equal(bytes, await firstResponse.Content.ReadAsByteArrayAsync());
        Assert.Equal(bytes, await secondResponse.Content.ReadAsByteArrayAsync());
    }

    [Theory]
    [InlineData("/api/technical-sheets/")]
    [InlineData("/api/technical-sheets/1/file")]
    public async Task AdministrativeTechnicalSheetEndpointsStillRequireAuthentication(string path)
    {
        using var client = _factory.CreateClient();
        using var response = await client.GetAsync(path);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task PublicProductFiltersWorkWithSearchCategoryBrandAndSafeOrdering()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var bySearch = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?search=excavadora"));
        var byCategory = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?category=maquinaria"));
        var byBrand = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?brand=acme"));
        var byType = await ReadJsonAsync<JsonElement>(await client.GetAsync($"/api/public/products/?product_type={ProductTypes.Machinery}&condition={ProductConditions.Used}&stock_status={StockStatuses.Available}&ordering=price"));
        var unsafeOrdering = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?ordering=created_at"));

        Assert.Single(bySearch.EnumerateArray());
        Assert.Single(byCategory.EnumerateArray());
        Assert.Single(byBrand.EnumerateArray());
        Assert.Single(byType.EnumerateArray());
        Assert.Single(unsafeOrdering.EnumerateArray());
    }

    [Fact]
    public async Task SoldProductIsExcludedFromPublicListsSearchAndDetail()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var products = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/"));
        var search = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/products/?search=vendida"));
        var soldFilter = await ReadJsonAsync<JsonElement>(await client.GetAsync($"/api/public/products/?stock_status={StockStatuses.Sold}"));
        var bySlug = await client.GetAsync("/api/public/products/excavadora-vendida/");
        var byId = await client.GetAsync("/api/public/products/6/");

        Assert.Single(products.EnumerateArray());
        Assert.Equal("excavadora", products[0].GetProperty("slug").GetString());
        Assert.Empty(search.EnumerateArray());
        Assert.Empty(soldFilter.EnumerateArray());
        Assert.Equal(HttpStatusCode.NotFound, bySlug.StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, byId.StatusCode);
        Assert.Empty(await bySlug.Content.ReadAsByteArrayAsync());
        Assert.Empty(await byId.Content.ReadAsByteArrayAsync());
    }

    [Fact]
    public async Task PublicPromotionHomeSpecsAndImagesOnlyExposePublishedActiveData()
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var promotions = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/promotions/"));
        var homeItems = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/home-section-items/"));
        var specs = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-specs/?product=1"));
        var hiddenSpecs = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-specs/?product=3"));
        var images = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-images/?product=1"));
        var hiddenImages = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-images/?product=3"));
        var soldSpecs = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-specs/?product=6"));
        var soldImages = await ReadJsonAsync<JsonElement>(await client.GetAsync("/api/public/product-images/?product=6"));

        Assert.Equal(2, promotions.GetArrayLength());
        Assert.Equal("Promo vigente", promotions[0].GetProperty("title").GetString());
        Assert.Single(homeItems.EnumerateArray());
        Assert.Single(specs.EnumerateArray());
        Assert.Empty(hiddenSpecs.EnumerateArray());
        Assert.Single(images.EnumerateArray());
        Assert.Empty(hiddenImages.EnumerateArray());
        Assert.Empty(soldSpecs.EnumerateArray());
        Assert.Empty(soldImages.EnumerateArray());
        Assert.DoesNotContain(promotions.EnumerateArray(), promotion => promotion.GetProperty("title").GetString() == "Promo vendida");
        Assert.DoesNotContain(homeItems.EnumerateArray(), item => item.GetProperty("product").GetProperty("slug").GetString() == "excavadora-vendida");
    }

    [Theory]
    [InlineData("/api/products/")]
    [InlineData("/api/categories/")]
    public async Task AdminReadEndpointsStillRequireBearerToken(string path)
    {
        await SeedPublicCatalogDataAsync();
        using var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    private async Task SeedPublicCatalogDataAsync()
    {
        await _factory.SeedCommercialDataAsync();

        using var scope = _factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var spareProduct = await dbContext.Products.SingleOrDefaultAsync(product => product.Slug == "filtro");
        if (spareProduct is not null)
        {
            spareProduct.IsPublished = false;
        }

        if (await dbContext.Products.AnyAsync(product => product.Slug == "borrador"))
        {
            await dbContext.SaveChangesAsync();
            return;
        }

        var inactiveCategory = new Category { Id = 4, Name = "Categoría Inactiva", Slug = "categoria-inactiva", IsActive = false, Description = "No pública", Order = 3 };
        var inactiveBrand = new Brand { Id = 2, Name = "Marca Inactiva", Slug = "marca-inactiva", IsActive = false };
        var draftProduct = new Product { Id = 3, Name = "Borrador", Slug = "borrador", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = false };
        var inactiveCategoryProduct = new Product { Id = 4, Name = "Producto Inactivo", Slug = "producto-inactivo", Category = inactiveCategory, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };
        var inactiveBrandProduct = new Product { Id = 5, Name = "Marca Oculta", Slug = "marca-oculta", CategoryId = 1, Brand = inactiveBrand, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Available, IsPublished = true };
        var soldProduct = new Product { Id = 6, Name = "Excavadora Vendida", Slug = "excavadora-vendida", CategoryId = 1, BrandId = 1, ProductType = ProductTypes.Machinery, Condition = ProductConditions.Used, StockStatus = StockStatuses.Sold, IsPublished = true };
        dbContext.Categories.Add(inactiveCategory);
        dbContext.Brands.Add(inactiveBrand);
        dbContext.Products.AddRange(draftProduct, inactiveCategoryProduct, inactiveBrandProduct, soldProduct);
        dbContext.ProductImages.AddRange(
            new ProductImage { Id = 1, ProductId = 1, Image = "/media/excavadora.jpg", AltText = "Excavadora", IsMain = true },
            new ProductImage { Id = 2, Product = draftProduct, Image = "/media/borrador.jpg", AltText = "Borrador", IsMain = true },
            new ProductImage { Id = 3, Product = soldProduct, Image = "/media/vendida.jpg", AltText = "Vendida", IsMain = true });
        dbContext.ProductSpecs.AddRange(
            new ProductSpec { Id = 2, Product = draftProduct, Key = "Oculta", Value = "No", Unit = string.Empty },
            new ProductSpec { Id = 3, Product = soldProduct, Key = "Estado", Value = "Vendida", Unit = string.Empty });
        dbContext.Promotions.AddRange(
            new Promotion { Id = 1, Title = "Promo vigente", ProductId = 1, IsActive = true, StartsAt = DateTimeOffset.UtcNow.AddDays(-1), EndsAt = DateTimeOffset.UtcNow.AddDays(1), Order = 1 },
            new Promotion { Id = 2, Title = "Promo inactiva", ProductId = 1, IsActive = false, Order = 2 },
            new Promotion { Id = 3, Title = "Promo borrador", Product = draftProduct, IsActive = true, Order = 3 },
            new Promotion { Id = 4, Title = "Promo vendida", Product = soldProduct, IsActive = true, Order = 4 },
            new Promotion { Id = 5, Title = "Promo general", Product = null, IsActive = true, Order = 5 });
        dbContext.HomeSectionItems.AddRange(
            new HomeSectionItem { Id = 2, Section = HomeSections.MachineryPromotions, Product = draftProduct, Position = 2, IsActive = true },
            new HomeSectionItem { Id = 3, Section = HomeSections.SparePartsOffers, Product = soldProduct, Position = 3, IsActive = true });
        await dbContext.SaveChangesAsync();
    }

    private async Task AttachTechnicalSheetAsync(
        string storageKey,
        string originalFileName,
        string contentType,
        byte[] bytes,
        params int[] productIds)
    {
        if (!storageKey.Contains("missing", StringComparison.Ordinal)) _storage.Files[storageKey] = bytes;
        if (productIds.Length == 0) productIds = [1];
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        var products = await db.Products.Where(product => productIds.Contains(product.Id)).ToListAsync();
        var sheet = CreateTechnicalSheet(storageKey, originalFileName, contentType, bytes.Length);
        foreach (var product in products) product.TechnicalSheet = sheet;
        await db.SaveChangesAsync();
    }

    private static TechnicalSheet CreateTechnicalSheet(string storageKey, string originalFileName, string contentType, long sizeBytes) => new()
    {
        Name = "Manual público",
        OriginalFileName = originalFileName,
        StorageKey = storageKey,
        ContentType = contentType,
        SizeBytes = sizeBytes,
        CreatedAt = DateTimeOffset.Parse("2026-01-01T00:00:00Z"),
        UpdatedAt = DateTimeOffset.Parse("2026-01-02T00:00:00Z")
    };

    private static async Task AssertSafeNotFoundAsync(HttpClient client, string path)
    {
        using var response = await client.GetAsync(path);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        AssertSafePublicPayload(body);
        Assert.DoesNotContain("exception", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("invalid", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("technical sheet", body, StringComparison.OrdinalIgnoreCase);
    }

    private static void AssertSafePublicPayload(string body)
    {
        Assert.DoesNotContain("StorageKey", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("storage_key", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("uploads", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("/api/technical-sheets", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("ContentRootPath", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("/tmp/", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("/var/", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("C:\\", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("credential", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("token", body, StringComparison.OrdinalIgnoreCase);
    }

    private static void AssertTechnicalData(JsonElement product)
    {
        Assert.Equal(7.79m, product.GetProperty("working_height_m").GetDecimal());
        Assert.Equal(227m, product.GetProperty("maximum_load_capacity_kg").GetDecimal());
        Assert.Equal(ProductPowerSources.Electric24V, product.GetProperty("power_source").GetString());
        Assert.Equal(ProductTerrainTypes.IndoorSmooth, product.GetProperty("terrain_type").GetString());
    }

    private static async Task<T> ReadJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        var payload = await response.Content.ReadFromJsonAsync<T>();
        Assert.True(payload is not null, $"Expected JSON response for {typeof(T).Name}. Body: {body}");
        return payload!;
    }

    private sealed class MemoryTechnicalSheetStorage : ITechnicalSheetStorage
    {
        public Dictionary<string, byte[]> Files { get; } = new(StringComparer.Ordinal);
        public HashSet<string> InvalidKeys { get; } = new(StringComparer.Ordinal);
        public bool LastOpenedStreamWasSeekable { get; private set; }
        public Task<string> SaveAsync(Stream content, string extension, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task DeleteAsync(string storageKey, CancellationToken cancellationToken) => Task.CompletedTask;
        public Task<Stream?> OpenReadAsync(string storageKey, CancellationToken cancellationToken)
        {
            if (InvalidKeys.Contains(storageKey)) throw new ArgumentException("Invalid storage key.", nameof(storageKey));
            Stream? stream = Files.TryGetValue(storageKey, out var bytes) ? new MemoryStream(bytes, writable: false) : null;
            LastOpenedStreamWasSeekable = stream?.CanSeek == true;
            return Task.FromResult(stream);
        }
    }
}
