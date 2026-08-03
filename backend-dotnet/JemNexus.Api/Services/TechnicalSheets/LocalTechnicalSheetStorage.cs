namespace JemNexus.Api.Services.TechnicalSheets;

public sealed class LocalTechnicalSheetStorage(IHostEnvironment environment) : ITechnicalSheetStorage
{
    private readonly string _root = Path.Combine(environment.ContentRootPath, "uploads", "technical-sheets");

    public async Task<string> SaveAsync(Stream content, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(_root);
        var storageKey = $"{Guid.NewGuid():N}.pdf";
        await using var output = new FileStream(GetSafePath(storageKey), FileMode.CreateNew, FileAccess.Write, FileShare.None, 81920, true);
        await content.CopyToAsync(output, cancellationToken);
        return storageKey;
    }

    public Task<Stream?> OpenReadAsync(string storageKey, CancellationToken cancellationToken)
    {
        var path = GetSafePath(storageKey);
        Stream? stream = File.Exists(path) ? new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true) : null;
        return Task.FromResult(stream);
    }

    public Task DeleteAsync(string storageKey, CancellationToken cancellationToken)
    {
        var path = GetSafePath(storageKey);
        if (File.Exists(path)) File.Delete(path);
        return Task.CompletedTask;
    }

    private string GetSafePath(string storageKey)
    {
        if (string.IsNullOrWhiteSpace(storageKey) || Path.GetFileName(storageKey) != storageKey)
            throw new InvalidOperationException("Invalid technical sheet storage key.");
        var path = Path.GetFullPath(Path.Combine(_root, storageKey));
        if (!path.StartsWith(Path.GetFullPath(_root) + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new InvalidOperationException("Invalid technical sheet storage key.");
        return path;
    }
}
