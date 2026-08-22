using JemNexus.Api.Data;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using JemNexus.Api.Services.ProductImages;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace JemNexus.Api.Endpoints;

public static class PublicMediaEndpoints
{
    public static IEndpointRouteBuilder MapPublicMediaEndpoints(this IEndpointRouteBuilder app)
    {
        var options = app.ServiceProvider.GetRequiredService<IOptions<UploadOptions>>().Value;
        var basePath = ProductImagePath.NormalizePublicBasePath(options.PublicBasePath);
        app.MapMethods($"{basePath}/product-images/{{productId:int}}/{{fileName}}", [HttpMethods.Get, HttpMethods.Head], GetProductImageAsync)
            .AllowAnonymous()
            .WithName("PublicProductImage");
        return app;
    }

    private static async Task<IResult> GetProductImageAsync(
        int productId,
        string fileName,
        JemNexusDbContext dbContext,
        IProductImageStorage storage,
        IOptions<UploadOptions> options,
        HttpContext httpContext,
        CancellationToken cancellationToken)
    {
        var contentType = Path.GetExtension(fileName).ToLowerInvariant() switch
        {
            ".jpg" or ".jpeg" => "image/jpeg",
            ".png" => "image/png",
            ".webp" => "image/webp",
            _ => null
        };
        var expectedPath = ProductImagePath.BuildPublicPath(options.Value.PublicBasePath, productId, fileName);
        if (contentType is null || expectedPath is null) return Results.NotFound();

        var isRegisteredAndPublic = await PublicProductQuery.Apply(dbContext.Products.AsNoTracking())
            .Where(product => product.Id == productId)
            .SelectMany(product => product.Images)
            .AnyAsync(image => image.ProductId == productId && image.Image == expectedPath, cancellationToken);
        if (!isRegisteredAndPublic) return Results.NotFound();

        var stream = await storage.OpenReadAsync(expectedPath, cancellationToken);
        if (stream is null) return Results.NotFound();

        httpContext.Response.Headers.XContentTypeOptions = "nosniff";
        httpContext.Response.Headers.CacheControl = "public, max-age=0, must-revalidate";
        return Results.File(stream, contentType, enableRangeProcessing: true);
    }
}
