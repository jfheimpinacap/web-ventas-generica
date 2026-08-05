using JemNexus.Api.Options;
using Microsoft.Extensions.Options;

namespace JemNexus.Api.Services.ProductImages;

public sealed class LocalProductImageStorage(IHostEnvironment environment, IOptions<UploadOptions> options) : IProductImageStorage
{
    private readonly UploadOptions _options = options.Value;
    private string Root => string.IsNullOrWhiteSpace(_options.RootPath)
        ? Path.Combine(environment.ContentRootPath, "uploads")
        : _options.RootPath;
    private string ProductImagesRoot => Path.Combine(Root, "product-images");

    public async Task<StoredProductImage> SaveAsync(int productId, IFormFile file, CancellationToken cancellationToken)
    {
        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        var directory = Path.Combine(ProductImagesRoot, productId.ToString(System.Globalization.CultureInfo.InvariantCulture));
        Directory.CreateDirectory(directory);

        var storageKey = $"product-images/{productId}/{Guid.NewGuid():N}{extension}";
        var finalPath = GetSafeManagedPath(storageKey);
        var temporaryPath = Path.Combine(directory, $".{Guid.NewGuid():N}.tmp");

        try
        {
            await using (var output = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, 81920, true))
            {
                await file.CopyToAsync(output, cancellationToken);
            }

            File.Move(temporaryPath, finalPath, overwrite: false);
            return new StoredProductImage(ToPublicPath(storageKey), storageKey);
        }
        catch
        {
            if (File.Exists(temporaryPath)) File.Delete(temporaryPath);
            if (File.Exists(finalPath)) File.Delete(finalPath);
            throw;
        }
    }

    public Task DeleteIfManagedAsync(string publicPath, CancellationToken cancellationToken)
    {
        var basePath = NormalizeBasePath(_options.PublicBasePath);
        if (!publicPath.StartsWith(basePath + "/product-images/", StringComparison.OrdinalIgnoreCase)) return Task.CompletedTask;
        var relative = publicPath[basePath.Length..].TrimStart('/').Replace('/', Path.DirectorySeparatorChar);
        var path = Path.GetFullPath(Path.Combine(Root, relative));
        var root = Path.GetFullPath(Root);
        if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return Task.CompletedTask;
        if (File.Exists(path)) File.Delete(path);
        return Task.CompletedTask;
    }

    private string GetSafeManagedPath(string storageKey)
    {
        var normalized = storageKey.Replace('/', Path.DirectorySeparatorChar);
        var path = Path.GetFullPath(Path.Combine(Root, normalized));
        var root = Path.GetFullPath(Root);
        if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new InvalidOperationException("Invalid product image storage key.");
        return path;
    }

    private string ToPublicPath(string storageKey) => $"{NormalizeBasePath(_options.PublicBasePath)}/{storageKey.Replace('\\', '/')}";

    private static string NormalizeBasePath(string value)
    {
        var path = string.IsNullOrWhiteSpace(value) ? "/media" : value.Trim();
        return "/" + path.Trim('/');
    }
}
