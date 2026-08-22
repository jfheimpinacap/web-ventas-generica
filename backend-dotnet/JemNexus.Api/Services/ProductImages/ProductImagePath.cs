using System.Globalization;

namespace JemNexus.Api.Services.ProductImages;

internal static class ProductImagePath
{
    private const string DefaultPublicBasePath = "/media";

    internal static string NormalizePublicBasePath(string? value)
    {
        var path = string.IsNullOrWhiteSpace(value) ? DefaultPublicBasePath : value.Trim();
        path = path.Replace('\\', '/');
        if (Uri.TryCreate(path, UriKind.Absolute, out _)) return DefaultPublicBasePath;
        var segments = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length == 0 || segments.Any(segment => segment is "." or "..")) return DefaultPublicBasePath;
        return "/" + string.Join('/', segments);
    }

    internal static bool IsSafeFileName(string? fileName) =>
        !string.IsNullOrWhiteSpace(fileName)
        && fileName is not "." and not ".."
        && !fileName.Contains('/')
        && !fileName.Contains('\\')
        && !Path.IsPathRooted(fileName);

    internal static string? BuildPublicPath(string? publicBasePath, int productId, string? fileName)
    {
        if (productId <= 0 || !IsSafeFileName(fileName)) return null;
        return $"{NormalizePublicBasePath(publicBasePath)}/product-images/{productId.ToString(CultureInfo.InvariantCulture)}/{fileName}";
    }

    internal static string? GetManagedPhysicalPath(string rootPath, string? publicBasePath, string? publicPath)
    {
        var prefix = NormalizePublicBasePath(publicBasePath) + "/product-images/";
        if (string.IsNullOrWhiteSpace(publicPath) || !publicPath.StartsWith(prefix, StringComparison.Ordinal)) return null;
        var relative = publicPath[prefix.Length..].Split('/');
        if (relative.Length != 2 || !int.TryParse(relative[0], NumberStyles.None, CultureInfo.InvariantCulture, out var productId)
            || productId <= 0 || !IsSafeFileName(relative[1])) return null;

        var root = Path.GetFullPath(rootPath);
        var productImagesRoot = Path.GetFullPath(Path.Combine(root, "product-images"));
        var path = Path.GetFullPath(Path.Combine(productImagesRoot, relative[0], relative[1]));
        var boundary = productImagesRoot.EndsWith(Path.DirectorySeparatorChar)
            ? productImagesRoot : productImagesRoot + Path.DirectorySeparatorChar;
        return path.StartsWith(boundary, StringComparison.Ordinal) ? path : null;
    }
}
