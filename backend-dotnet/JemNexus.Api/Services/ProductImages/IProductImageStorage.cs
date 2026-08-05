namespace JemNexus.Api.Services.ProductImages;

public sealed record StoredProductImage(string PublicPath, string StorageKey);

public interface IProductImageStorage
{
    Task<StoredProductImage> SaveAsync(int productId, IFormFile file, CancellationToken cancellationToken);
    Task DeleteIfManagedAsync(string publicPath, CancellationToken cancellationToken);
}
