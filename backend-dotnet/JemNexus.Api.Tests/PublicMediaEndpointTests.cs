using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class PublicMediaEndpointTests
{
    private const string TestPassword = "DummyPassword123!";
    private static readonly byte[] ImageBytes = [1, 2, 3, 4, 5, 6];

    [Fact]
    public async Task RegisteredPublicImageSupportsGetHeadAndRange()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var path = await SeedImageAsync(factory, productId: 101, fileName: "public.webp", brandState: true);
        using var client = factory.CreateClient();

        using var response = await client.GetAsync(path);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(ImageBytes, await response.Content.ReadAsByteArrayAsync());
        Assert.Equal("image/webp", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal("nosniff", response.Headers.GetValues("X-Content-Type-Options").Single());
        Assert.Equal("public, max-age=0, must-revalidate", response.Headers.CacheControl?.ToString());
        Assert.Null(response.Content.Headers.ContentDisposition);

        using var head = await client.SendAsync(new HttpRequestMessage(HttpMethod.Head, path));
        Assert.Equal(HttpStatusCode.OK, head.StatusCode);
        Assert.Equal("image/webp", head.Content.Headers.ContentType?.MediaType);
        Assert.Empty(await head.Content.ReadAsByteArrayAsync());

        using var rangeRequest = new HttpRequestMessage(HttpMethod.Get, path);
        rangeRequest.Headers.Range = new RangeHeaderValue(1, 3);
        using var range = await client.SendAsync(rangeRequest);
        Assert.Equal(HttpStatusCode.PartialContent, range.StatusCode);
        Assert.Equal(ImageBytes[1..4], await range.Content.ReadAsByteArrayAsync());
    }

    [Fact]
    public async Task PublicProductWithoutBrandHasAvailableImageAndIsRecheckedEachRequest()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var path = await SeedImageAsync(factory, 102, "brandless.jpg", brandState: null);
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync(path)).StatusCode);

        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            (await db.Products.SingleAsync(product => product.Id == 102)).IsPublished = false;
            await db.SaveChangesAsync();
        }

        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(path)).StatusCode);
    }

    [Theory]
    [InlineData(false, true, StockStatuses.Available)]
    [InlineData(true, false, StockStatuses.Available)]
    [InlineData(true, true, StockStatuses.Sold)]
    public async Task NonPublicProductImagesReturnUniformNotFound(bool published, bool categoryActive, string stockStatus)
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var path = await SeedImageAsync(factory, 103, "hidden.png", true, published, categoryActive, stockStatus);
        using var response = await factory.CreateClient().GetAsync(path);
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        Assert.Empty(await response.Content.ReadAsByteArrayAsync());
    }

    [Fact]
    public async Task InactiveBrandWrongAssociationChangedPathMissingFileAndUnknownFileReturnNotFound()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var inactive = await SeedImageAsync(factory, 104, "inactive.jpg", false);
        var valid = await SeedImageAsync(factory, 105, "valid.jpg", true);
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(inactive)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/media/product-images/999/valid.jpg")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/media/product-images/105/unknown.jpg")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/media/product-images/105/valid.svg")).StatusCode);

        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            (await db.ProductImages.SingleAsync(image => image.ProductId == 105)).Image = "/media/product-images/105/changed.jpg";
            await db.SaveChangesAsync();
        }
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(valid)).StatusCode);

        var missing = await SeedImageAsync(factory, 106, "missing.webp", true);
        File.Delete(factory.PhysicalUploadPath(missing));
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(missing)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/media/product-images/106/%2e%2e%2fmissing.webp")).StatusCode);
    }

    [Fact]
    public async Task TechnicalSheetDirectoryIsNotPubliclyServed()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var physical = Path.Combine(factory.UploadRoot, "technical-sheets", "private.pdf");
        Directory.CreateDirectory(Path.GetDirectoryName(physical)!);
        await File.WriteAllBytesAsync(physical, "%PDF-private"u8.ToArray());
        using var response = await factory.CreateClient().GetAsync("/media/technical-sheets/private.pdf");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task ConfiguredPublicBasePathIsTheOnlyMediaRoute()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory(publicBasePath: "/assets-media");
        var path = await SeedImageAsync(factory, 107, "configured.jpeg", null, publicBasePath: "/assets-media");
        using var client = factory.CreateClient();
        Assert.StartsWith("/assets-media/product-images/", path, StringComparison.Ordinal);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync(path)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(path.Replace("/assets-media/", "/media/", StringComparison.Ordinal))).StatusCode);
    }

    [Fact]
    public async Task AdministrativeImageEndpointRequiresCommercialReadAuthorization()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        await SeedImageAsync(factory, 108, "draft.jpg", true, published: false);
        var imageId = await GetImageIdAsync(factory, 108);
        using var anonymous = factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await anonymous.GetAsync($"/api/product-images/{imageId}/file")).StatusCode);

        await factory.SeedUnauthorizedUserAsync();
        using var viewer = await CreateAuthorizedClientAsync(factory, "viewer");
        Assert.Equal(HttpStatusCode.Forbidden, (await viewer.GetAsync($"/api/product-images/{imageId}/file")).StatusCode);
    }

    [Theory]
    [InlineData("demo")]
    [InlineData("support")]
    public async Task AuthorizedCommercialUsersCanReadUnpublishedImageWithSafeHeadersAndRange(string username)
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var publicPath = await SeedImageAsync(factory, 109, "draft.webp", true, published: false);
        var imageId = await GetImageIdAsync(factory, 109);
        using var client = await CreateAuthorizedClientAsync(factory, username);

        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(publicPath)).StatusCode);
        using var response = await client.GetAsync($"/api/product-images/{imageId}/file");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(ImageBytes, await response.Content.ReadAsByteArrayAsync());
        Assert.Equal("image/webp", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal("nosniff", response.Headers.GetValues("X-Content-Type-Options").Single());
        Assert.Equal("private, no-store", response.Headers.CacheControl?.ToString());
        Assert.Null(response.Content.Headers.ContentDisposition);

        using var request = new HttpRequestMessage(HttpMethod.Get, $"/api/product-images/{imageId}/file");
        request.Headers.Range = new RangeHeaderValue(2, 4);
        using var range = await client.SendAsync(request);
        Assert.Equal(HttpStatusCode.PartialContent, range.StatusCode);
        Assert.Equal(ImageBytes[2..5], await range.Content.ReadAsByteArrayAsync());
    }

    [Theory]
    [InlineData(StockStatuses.Sold, true, true)]
    [InlineData(StockStatuses.Available, false, true)]
    [InlineData(StockStatuses.Available, true, false)]
    public async Task AdminImageRemainsAvailableWhenPublicEligibilityFails(string stockStatus, bool categoryActive, bool brandActive)
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var publicPath = await SeedImageAsync(factory, 110, "restricted.png", brandActive, categoryActive: categoryActive, stockStatus: stockStatus);
        var imageId = await GetImageIdAsync(factory, 110);
        using var client = await CreateAuthorizedClientAsync(factory, "demo");
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(publicPath)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync($"/api/product-images/{imageId}/file")).StatusCode);
    }

    [Fact]
    public async Task AdminImageReturnsNotFoundForUnknownUnmanagedAndMissingFiles()
    {
        using var factory = new CommercialWriteEndpointTests.CommercialWriteApiFactory();
        var path = await SeedImageAsync(factory, 111, "managed.jpg", true);
        var imageId = await GetImageIdAsync(factory, 111);
        using var client = await CreateAuthorizedClientAsync(factory, "demo");
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/product-images/999999/file")).StatusCode);

        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            (await db.ProductImages.SingleAsync(image => image.Id == imageId)).Image = "/external/image.jpg";
            await db.SaveChangesAsync();
        }
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync($"/api/product-images/{imageId}/file")).StatusCode);

        var missingPath = await SeedImageAsync(factory, 112, "missing.jpg", true);
        var missingId = await GetImageIdAsync(factory, 112);
        File.Delete(factory.PhysicalUploadPath(missingPath));
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync($"/api/product-images/{missingId}/file")).StatusCode);
        Assert.True(File.Exists(factory.PhysicalUploadPath(path)));
    }

    private static async Task<int> GetImageIdAsync(CommercialWriteEndpointTests.CommercialWriteApiFactory factory, int productId)
    {
        using var scope = factory.Services.CreateScope();
        return await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().ProductImages
            .Where(image => image.ProductId == productId).Select(image => image.Id).SingleAsync();
    }

    private static async Task<HttpClient> CreateAuthorizedClientAsync(CommercialWriteEndpointTests.CommercialWriteApiFactory factory, string username)
    {
        var client = factory.CreateClient();
        using var loginResponse = await client.PostAsJsonAsync("/api/auth/login", new { username, password = TestPassword });
        var payload = await loginResponse.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal(HttpStatusCode.OK, loginResponse.StatusCode);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", payload.GetProperty("access").GetString());
        return client;
    }

    private static async Task<string> SeedImageAsync(
        CommercialWriteEndpointTests.CommercialWriteApiFactory factory,
        int productId,
        string fileName,
        bool? brandState,
        bool published = true,
        bool categoryActive = true,
        string stockStatus = StockStatuses.Available,
        string publicBasePath = "/media")
    {
        var category = new Category { Id = productId, Name = $"Category {productId}", Slug = $"category-{productId}", ProductType = ProductTypes.Machinery, IsActive = categoryActive };
        Brand? brand = brandState is null ? null : new Brand { Id = productId, Name = $"Brand {productId}", Slug = $"brand-{productId}", IsActive = brandState.Value };
        var path = $"{publicBasePath}/product-images/{productId}/{fileName}";
        using (var scope = factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            db.Products.Add(new Product
            {
                Id = productId, Name = $"Product {productId}", Slug = $"product-{productId}", Category = category,
                Brand = brand, ProductType = ProductTypes.Machinery, Condition = ProductConditions.New,
                StockStatus = stockStatus, IsPublished = published,
                Images = [new ProductImage { Image = path, AltText = "Test", IsMain = true }]
            });
            await db.SaveChangesAsync();
        }
        var physical = factory.PhysicalUploadPath(path.Replace(publicBasePath, "/media", StringComparison.Ordinal));
        Directory.CreateDirectory(Path.GetDirectoryName(physical)!);
        await File.WriteAllBytesAsync(physical, ImageBytes);
        return path;
    }
}
