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

        var fileName = $"{Guid.NewGuid():N}{extension}";
        var storageKey = $"product-images/{productId}/{fileName}";
        var publicPath = ProductImagePath.BuildPublicPath(_options.PublicBasePath, productId, fileName)
            ?? throw new InvalidOperationException("Invalid product image path.");
        var finalPath = ProductImagePath.GetManagedPhysicalPath(Root, _options.PublicBasePath, publicPath)
            ?? throw new InvalidOperationException("Invalid product image storage key.");
        var temporaryPath = Path.Combine(directory, $".{Guid.NewGuid():N}.tmp");

        try
        {
            await using (var output = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, 81920, true))
            {
                await file.CopyToAsync(output, cancellationToken);
            }

            File.Move(temporaryPath, finalPath, overwrite: false);
            return new StoredProductImage(publicPath, storageKey);
        }
        catch
        {
            if (File.Exists(temporaryPath)) File.Delete(temporaryPath);
            if (File.Exists(finalPath)) File.Delete(finalPath);
            throw;
        }
    }

    public Task<Stream?> OpenReadAsync(string publicPath, CancellationToken cancellationToken)
    {
        var path = ProductImagePath.GetManagedPhysicalPath(Root, _options.PublicBasePath, publicPath);
        if (path is null || !File.Exists(path)) return Task.FromResult<Stream?>(null);
        Stream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, FileOptions.Asynchronous | FileOptions.SequentialScan);
        return Task.FromResult<Stream?>(stream);
    }

    public Task DeleteIfManagedAsync(string publicPath, CancellationToken cancellationToken)
    {
        var path = ProductImagePath.GetManagedPhysicalPath(Root, _options.PublicBasePath, publicPath);
        if (path is null) return Task.CompletedTask;
        if (File.Exists(path)) File.Delete(path);
        return Task.CompletedTask;
    }
}
