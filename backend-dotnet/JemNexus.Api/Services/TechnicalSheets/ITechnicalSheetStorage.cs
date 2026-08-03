namespace JemNexus.Api.Services.TechnicalSheets;

public interface ITechnicalSheetStorage
{
    Task<string> SaveAsync(Stream content, CancellationToken cancellationToken);
    Task<Stream?> OpenReadAsync(string storageKey, CancellationToken cancellationToken);
    Task DeleteAsync(string storageKey, CancellationToken cancellationToken);
}
