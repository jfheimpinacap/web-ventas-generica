using JemNexus.Api.Models;

namespace JemNexus.Api.Services;

internal static class PublicProductQuery
{
    internal static IQueryable<Product> Apply(IQueryable<Product> query) => query
        .Where(product => product.IsPublished)
        .Where(product => product.Category.IsActive)
        .Where(product => product.Brand == null || product.Brand.IsActive)
        .Where(product => product.StockStatus != StockStatuses.Sold);
}
