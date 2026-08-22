using Microsoft.AspNetCore.RateLimiting;
using System.ComponentModel.DataAnnotations;
using System.Security.Claims;
using JemNexus.Api.Contracts.Admin;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static class AdminCommercialQuoteEndpoints
{
    private const int MaximumPageSize = 100;

    public static IEndpointRouteBuilder MapAdminCommercialQuoteEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/admin/commercial-quotes").RequireAuthorization("RequireSellerOrSupportAdmin").WithTags("Admin commercial quotes");
        group.MapGet("", ListAsync);
        group.MapGet("/{id:int}", GetAsync);
        group.MapPost("/issue", IssueAsync).RequireRateLimiting(RateLimitPolicies.QuoteIssue).RequireAuthorization(policy => policy.RequireRole(AppRoles.Seller));
        return endpoints;
    }

    private static async Task<IResult> ListAsync(ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct, string? search, string? currency, string? status, [FromQuery(Name = "sale_condition")] string? saleCondition, int page = 1, [FromQuery(Name = "page_size")] int pageSize = 20)
    {
        var errors = new Dictionary<string, string[]>();
        if (page < 1 || pageSize is < 1 or > MaximumPageSize) errors["pagination"] = [$"page debe ser positivo y page_size debe estar entre 1 y {MaximumPageSize}."];
        if (currency is not null && currency is not (CommercialQuoteCurrencies.Clp or CommercialQuoteCurrencies.Usd)) errors["currency"] = ["Moneda no válida."];
        if (saleCondition is not null && saleCondition is not (CommercialQuoteSaleConditions.Cash or CommercialQuoteSaleConditions.Credit30Days)) errors["sale_condition"] = ["Condición de venta no válida."];
        if (status is not null && status is not (CommercialQuoteStatuses.Draft or CommercialQuoteStatuses.Issued)) errors["status"] = ["Estado no válido."];
        if (errors.Count > 0) return Results.ValidationProblem(errors);

        var support = principal.IsInRole(AppRoles.SupportAdmin);
        var userId = UserId(principal);
        var query = db.CommercialQuotes.AsNoTracking().AsQueryable();
        if (!support) query = query.Where(quote => quote.ResponsibleSellerId == userId);
        if (currency is not null) query = query.Where(quote => quote.Currency == currency);
        if (saleCondition is not null) query = query.Where(quote => quote.SaleCondition == saleCondition);
        if (status is not null) query = query.Where(quote => quote.Status == status);
        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = CustomerTextNormalizer.Search(search);
            var rut = new string(search.Where(char.IsLetterOrDigit).ToArray()).ToUpperInvariant();
            query = query.Where(quote => quote.CustomerBusinessName.ToUpper().Contains(term)
                || quote.CustomerRut.Replace("-", "").Replace(".", "").ToUpper().Contains(rut)
                || quote.CustomerContactName.ToUpper().Contains(term)
                || (quote.Folio != null && quote.Folio.ToUpper().Contains(term))
                || (support && quote.ResponsibleSellerCode.ToUpper().Contains(term)));
        }

        var count = await query.CountAsync(ct);
        var results = await query.OrderByDescending(quote => quote.UpdatedAt).ThenByDescending(quote => quote.Id)
            .Skip((page - 1) * pageSize).Take(pageSize)
            .Select(quote => new CommercialQuoteSummaryResponse(quote.Id, quote.Status, quote.Folio, quote.IssuedAtUtc, quote.IssuedOn, quote.Currency, quote.CustomerBusinessName, quote.CustomerRut, quote.CustomerContactName, quote.ResponsibleSellerName, quote.ResponsibleSellerCode, quote.NetAmount, quote.TaxAmount, quote.TotalAmount, quote.Items.Count, quote.CreatedAt, quote.UpdatedAt)).ToListAsync(ct);
        return Results.Ok(new CommercialQuotePageResponse(results, page, pageSize, count));
    }

    private static async Task<IResult> GetAsync(int id, ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct)
    {
        var query = db.CommercialQuotes.AsNoTracking().Include(quote => quote.Items).Where(quote => quote.Id == id);
        if (!principal.IsInRole(AppRoles.SupportAdmin)) query = query.Where(quote => quote.ResponsibleSellerId == UserId(principal));
        var quote = await query.SingleOrDefaultAsync(ct);
        return quote is null ? Results.NotFound() : Results.Ok(ToDetail(quote));
    }

    private static async Task<IResult> IssueAsync(CommercialQuoteIssueRequest request, ClaimsPrincipal principal, JemNexusDbContext db, TimeProvider timeProvider, CancellationToken ct)
    {
        var seller = await ActiveSellerAsync(principal, db, ct);
        if (seller is null) return Results.Forbid();
        var prepared = await PrepareAsync(request, db, ct);
        if (prepared.Errors.Count > 0) return Results.ValidationProblem(prepared.Errors);
        var quote = prepared.Quote!;
        quote.ResponsibleSellerId = seller.Id;
        quote.ResponsibleSellerName = string.IsNullOrWhiteSpace(seller.FullName) ? seller.Username : seller.FullName.Trim();
        quote.ResponsibleSellerCode = seller.SellerCode!;
        var errors = await ValidateForIssueAsync(quote, db, ct);
        if (errors.Count > 0) return Results.ValidationProblem(errors);
        CommercialQuoteCalculator.Calculate(quote);
        await using var transaction = db.Database.IsRelational()
            ? await db.Database.BeginTransactionAsync(CommercialQuoteFolioAllocator.SqlServerIsolationLevel, ct) : null;
        var (utc, localDate) = ChileTime.Current(timeProvider);
        var sequence = await CommercialQuoteFolioAllocator.NextAsync(db, localDate.Year, ct);
        quote.Issue(localDate.Year, sequence, utc, localDate);
        db.CommercialQuotes.Add(quote);
        await db.SaveChangesAsync(ct);
        if (transaction is not null) await transaction.CommitAsync(ct);
        return Results.Created($"/api/admin/commercial-quotes/{quote.Id}", ToDetail(quote));
    }

    private static async Task<Dictionary<string, string[]>> ValidateForIssueAsync(CommercialQuote quote, JemNexusDbContext db, CancellationToken ct)
    {
        var errors = new Dictionary<string, string[]>();
        if (quote.Items.Count == 0) errors["items"] = ["La cotización debe contener al menos un ítem."];
        if (!quote.Items.OrderBy(item => item.Position).Select(item => item.Position).SequenceEqual(Enumerable.Range(1, quote.Items.Count))) errors["items"] = ["Las posiciones de los ítems no son coherentes."];
        if (quote.Items.Any(item => decimal.Round(item.DiscountPercent, 2) != item.DiscountPercent)) errors["items"] = ["Los descuentos deben usar hasta dos decimales."];
        try { CommercialQuoteCalculator.Calculate(quote); }
        catch (ArgumentException exception) { errors["quote"] = [exception.Message]; }
        var catalogIds = quote.Items.Where(item => item.Origin == CommercialQuoteItemOrigins.Catalog && item.ProductId.HasValue).Select(item => item.ProductId!.Value).Distinct().ToList();
        if (catalogIds.Count > 0)
        {
            var available = await db.Products.AsNoTracking().Where(product => catalogIds.Contains(product.Id) && product.IsPublished && product.StockStatus != StockStatuses.Sold).Select(product => product.Id).ToListAsync(ct);
            if (catalogIds.Except(available).Any()) errors["items"] = ["Uno o más productos de catálogo ya no están disponibles."];
        }
        return errors;
    }

    private static async Task<PreparedQuote> PrepareAsync(CommercialQuoteInput request, JemNexusDbContext db, CancellationToken ct)
    {
        var errors = new Dictionary<string, string[]>();
        if (request.CustomerProfileId is int profileId && !await db.CustomerProfiles.AsNoTracking().AnyAsync(profile => profile.Id == profileId, ct)) errors["customer_profile_id"] = ["El perfil de cliente no existe."];
        var quote = new CommercialQuote
        {
            CustomerProfileId = request.CustomerProfileId,
            CustomerBusinessName = CustomerTextNormalizer.Visible(request.CustomerBusinessName), CustomerRut = request.CustomerRut ?? string.Empty,
            CustomerBusinessActivity = CustomerTextNormalizer.Visible(request.CustomerBusinessActivity), CustomerAddress = CustomerTextNormalizer.Visible(request.CustomerAddress),
            CustomerPhone = CustomerTextNormalizer.Visible(request.CustomerPhone), CustomerCityOrCommune = CustomerTextNormalizer.Visible(request.CustomerCityOrCommune),
            CustomerContactName = CustomerTextNormalizer.Visible(request.CustomerContactName), CustomerEmail = CustomerTextNormalizer.Optional(request.CustomerEmail),
            Currency = request.Currency ?? string.Empty, SaleCondition = request.SaleCondition ?? string.Empty,
            ValidityDays = request.ValidityDays ?? CommercialQuoteRules.DefaultValidityDays, DetailedDescription = CustomerTextNormalizer.Optional(request.DetailedDescription)
        };
        ValidateText(errors, "customer_business_name", quote.CustomerBusinessName, 2, 200);
        ValidateText(errors, "customer_business_activity", quote.CustomerBusinessActivity, 2, 200);
        ValidateText(errors, "customer_address", quote.CustomerAddress, 3, 300);
        ValidateText(errors, "customer_phone", quote.CustomerPhone, 5, 30);
        ValidateText(errors, "customer_city_or_commune", quote.CustomerCityOrCommune, 2, 120);
        ValidateText(errors, "customer_contact_name", quote.CustomerContactName, 2, 200);
        if (!ChileanRut.TryNormalize(quote.CustomerRut, out var normalizedRut)) errors["customer_rut"] = [ChileanRut.InvalidMessage]; else quote.CustomerRut = normalizedRut;
        if (quote.CustomerEmail is not null && (quote.CustomerEmail.Length > 254 || !new EmailAddressAttribute().IsValid(quote.CustomerEmail))) errors["customer_email"] = ["El correo electrónico no es válido."];
        if (quote.Currency is not (CommercialQuoteCurrencies.Clp or CommercialQuoteCurrencies.Usd)) errors["currency"] = ["Moneda no válida."];
        if (quote.SaleCondition is not (CommercialQuoteSaleConditions.Cash or CommercialQuoteSaleConditions.Credit30Days)) errors["sale_condition"] = ["Condición de venta no válida."];
        if (quote.ValidityDays <= 0) errors["validity_days"] = ["La vigencia debe ser positiva."];
        if (quote.DetailedDescription?.Length > CommercialQuoteRules.DetailedDescriptionMaxLength) errors["detailed_description"] = [$"La descripción no puede superar {CommercialQuoteRules.DetailedDescriptionMaxLength} caracteres."];
        if (request.Items is null) errors["items"] = ["items es obligatorio (puede ser un arreglo vacío)."];

        var inputs = request.Items ?? [];
        var catalogIds = inputs.Where(item => item.Source == CommercialQuoteItemOrigins.Catalog && item.ProductId.HasValue).Select(item => item.ProductId!.Value).Distinct().ToList();
        var products = await db.Products.AsNoTracking().Include(product => product.Brand).Where(product => catalogIds.Contains(product.Id)).ToDictionaryAsync(product => product.Id, ct);
        for (var index = 0; index < inputs.Count; index++)
        {
            var input = inputs[index]; var key = $"items[{index}]";
            if (input.Quantity <= 0) errors[$"{key}.quantity"] = ["La cantidad debe ser positiva."];
            if (input.UnitNetAmount <= 0) errors[$"{key}.unit_net_amount"] = ["El precio neto debe ser positivo."];
            var discount = input.DiscountPercent ?? 0m;
            if (discount is < 0 or > 100 || decimal.Round(discount, 2) != discount) errors[$"{key}.discount_percent"] = ["El descuento debe estar entre 0 y 100 y usar hasta dos decimales."];
            var item = new CommercialQuoteItem { Position = index + 1, Origin = input.Source ?? string.Empty, Quantity = input.Quantity, UnitNetAmount = input.UnitNetAmount, DiscountPercent = discount };
            if (input.Source == CommercialQuoteItemOrigins.Catalog)
            {
                if (input.ProductId is null) errors[$"{key}.product_id"] = ["El producto es obligatorio para un ítem de catálogo."];
                else if (!products.TryGetValue(input.ProductId.Value, out var product) || !product.IsPublished || product.StockStatus == StockStatuses.Sold) errors[$"{key}.product_id"] = ["El producto no existe o no está disponible para cotizar."];
                else { item.ProductId = product.Id; item.ProductName = product.Name; item.BrandName = product.Brand?.Name; item.ModelName = product.Model; }
            }
            else if (input.Source == CommercialQuoteItemOrigins.FreeText)
            {
                if (input.ProductId is not null) errors[$"{key}.product_id"] = ["Un ítem libre no puede referenciar un producto."];
                item.ProductName = CustomerTextNormalizer.Visible(input.ProductName); item.BrandName = CustomerTextNormalizer.Optional(input.BrandName); item.ModelName = CustomerTextNormalizer.Optional(input.ModelName);
                ValidateText(errors, $"{key}.product_name", item.ProductName, 1, 220);
            }
            else errors[$"{key}.source"] = ["Origen no válido."];
            quote.Items.Add(item);
        }
        return new PreparedQuote(errors.Count == 0 ? quote : null, errors);
    }

    private static async Task<AppUser?> ActiveSellerAsync(ClaimsPrincipal principal, JemNexusDbContext db, CancellationToken ct) =>
        await db.AppUsers.SingleOrDefaultAsync(user => user.Id == UserId(principal) && user.IsActive && user.Role == AppRoles.Seller && user.SellerCode != null, ct);
    private static int UserId(ClaimsPrincipal principal) => int.TryParse(principal.FindFirstValue(ClaimTypes.NameIdentifier) ?? principal.FindFirstValue("sub"), out var id) ? id : 0;
    private static void ValidateText(Dictionary<string, string[]> errors, string key, string value, int min, int max) { if (value.Length < min || value.Length > max) errors[key] = [$"El campo debe tener entre {min} y {max} caracteres."]; }
    private static CommercialQuoteDetailResponse ToDetail(CommercialQuote quote) => new(quote.Id, quote.Status, quote.Folio, quote.IssuedAtUtc, quote.IssuedOn, quote.CustomerProfileId, quote.CustomerBusinessName, quote.CustomerRut, quote.CustomerBusinessActivity, quote.CustomerAddress, quote.CustomerPhone, quote.CustomerCityOrCommune, quote.CustomerContactName, quote.CustomerEmail, quote.ResponsibleSellerName, quote.ResponsibleSellerCode, quote.Currency, quote.SaleCondition, quote.ValidityDays, quote.DetailedDescription, quote.TaxRatePercent, quote.NetAmount, quote.TaxAmount, quote.TotalAmount, quote.CreatedAt, quote.UpdatedAt, quote.Items.OrderBy(item => item.Position).Select(item => new CommercialQuoteItemResponse(item.Id, item.Position, item.Origin, item.ProductId, item.ProductName, item.BrandName, item.ModelName, item.Quantity, item.UnitNetAmount, item.DiscountPercent, item.FinalUnitNetAmount, item.LineNetAmount)).ToList());
    private sealed record PreparedQuote(CommercialQuote? Quote, Dictionary<string, string[]> Errors);
}
