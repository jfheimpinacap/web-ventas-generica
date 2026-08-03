using JemNexus.Api.Data;
using JemNexus.Api.Dtos;
using JemNexus.Api.Models;
using JemNexus.Api.Services.TechnicalSheets;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace JemNexus.Api.Endpoints;

public static class TechnicalSheetEndpoints
{
    public const long MaxFileSize = 10 * 1024 * 1024;
    public const int MaxNameLength = 220;

    public static IEndpointRouteBuilder MapTechnicalSheetEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/technical-sheets").RequireAuthorization("RequireCommercialWrite");
        group.MapGet("/", ListAsync);
        group.MapGet("/{id:int}", GetAsync);
        group.MapPost("/", CreateAsync).DisableAntiforgery();
        group.MapPatch("/{id:int}", RenameAsync);
        group.MapPost("/{id:int}/file", ReplaceFileAsync).DisableAntiforgery();
        group.MapGet("/{id:int}/file", DownloadAsync);
        group.MapDelete("/{id:int}", DeleteAsync);
        return endpoints;
    }

    private static async Task<IResult> ListAsync(string? search, JemNexusDbContext db, CancellationToken ct)
    {
        var query = db.TechnicalSheets.AsNoTracking();
        if (!string.IsNullOrWhiteSpace(search)) query = query.Where(x => x.Name.Contains(search.Trim()));
        var items = await query.OrderByDescending(x => x.UpdatedAt).ToListAsync(ct);
        return Results.Ok(items.Select(ToResponse));
    }

    private static async Task<IResult> GetAsync(int id, JemNexusDbContext db, CancellationToken ct)
    {
        var item = await db.TechnicalSheets.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
        return item is null ? Results.NotFound() : Results.Ok(ToResponse(item));
    }

    private static async Task<IResult> CreateAsync([FromForm] string? name, [FromForm] IFormFile? file, JemNexusDbContext db, ITechnicalSheetStorage storage, ILoggerFactory loggerFactory, CancellationToken ct)
    {
        var error = Validate(name, file);
        if (error is not null) return Results.BadRequest(new { detail = error });
        var storageKey = await storage.SaveAsync(file!.OpenReadStream(), ct);
        var item = new TechnicalSheet { Name = name!.Trim(), OriginalFileName = Path.GetFileName(file.FileName), StorageKey = storageKey, ContentType = file.ContentType, SizeBytes = file.Length };
        db.TechnicalSheets.Add(item);
        try { await db.SaveChangesAsync(ct); }
        catch (DbUpdateException exception)
        {
            db.Entry(item).State = EntityState.Detached;
            await DeleteAfterPersistenceFailureAsync(storage, storageKey, loggerFactory, ct);
            loggerFactory.CreateLogger(typeof(TechnicalSheetEndpoints)).LogError(exception, "Could not persist a new technical sheet.");
            return PersistenceFailure();
        }
        return Results.Created($"/api/technical-sheets/{item.Id}", ToResponse(item));
    }

    private static async Task<IResult> RenameAsync(int id, RenameTechnicalSheetRequest request, JemNexusDbContext db, CancellationToken ct)
    {
        var nameError = ValidateName(request.Name);
        if (nameError is not null) return Results.BadRequest(new { detail = nameError });
        var item = await db.TechnicalSheets.FindAsync([id], ct);
        if (item is null) return Results.NotFound();
        item.Name = request.Name!.Trim();
        await db.SaveChangesAsync(ct);
        return Results.Ok(ToResponse(item));
    }

    private static async Task<IResult> ReplaceFileAsync(int id, [FromForm] IFormFile? file, JemNexusDbContext db, ITechnicalSheetStorage storage, ILoggerFactory loggerFactory, CancellationToken ct)
    {
        var error = ValidateFile(file);
        if (error is not null) return Results.BadRequest(new { detail = error });
        var item = await db.TechnicalSheets.FindAsync([id], ct);
        if (item is null) return Results.NotFound();
        var oldValues = new
        {
            item.OriginalFileName,
            item.StorageKey,
            item.ContentType,
            item.SizeBytes,
            item.UpdatedAt
        };
        var newKey = await storage.SaveAsync(file!.OpenReadStream(), ct);
        item.StorageKey = newKey; item.OriginalFileName = Path.GetFileName(file.FileName); item.ContentType = file.ContentType; item.SizeBytes = file.Length;
        try { await db.SaveChangesAsync(ct); }
        catch (DbUpdateException exception)
        {
            item.OriginalFileName = oldValues.OriginalFileName;
            item.StorageKey = oldValues.StorageKey;
            item.ContentType = oldValues.ContentType;
            item.SizeBytes = oldValues.SizeBytes;
            item.UpdatedAt = oldValues.UpdatedAt;
            db.Entry(item).State = EntityState.Unchanged;
            await DeleteAfterPersistenceFailureAsync(storage, newKey, loggerFactory, ct);
            loggerFactory.CreateLogger(typeof(TechnicalSheetEndpoints)).LogError(exception, "Could not persist a technical sheet file replacement.");
            return PersistenceFailure();
        }
        await storage.DeleteAsync(oldValues.StorageKey, ct);
        return Results.Ok(ToResponse(item));
    }

    private static async Task<IResult> DownloadAsync(int id, JemNexusDbContext db, ITechnicalSheetStorage storage, CancellationToken ct, bool download = false)
    {
        var item = await db.TechnicalSheets.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
        if (item is null) return Results.NotFound();
        var stream = await storage.OpenReadAsync(item.StorageKey, ct);
        if (stream is null) return Results.NotFound();
        return Results.File(stream, item.ContentType, download ? item.OriginalFileName : null, enableRangeProcessing: true);
    }

    private static async Task<IResult> DeleteAsync(int id, JemNexusDbContext db, ITechnicalSheetStorage storage, CancellationToken ct)
    {
        var item = await db.TechnicalSheets.FindAsync([id], ct);
        if (item is null) return Results.NotFound();
        db.TechnicalSheets.Remove(item);
        await db.SaveChangesAsync(ct);
        await storage.DeleteAsync(item.StorageKey, ct);
        return Results.NoContent();
    }

    private static string? Validate(string? name, IFormFile? file) => ValidateName(name) ?? ValidateFile(file);
    private static IResult PersistenceFailure() => Results.Problem(statusCode: StatusCodes.Status500InternalServerError, title: "No se pudo guardar la ficha técnica.");
    private static async Task DeleteAfterPersistenceFailureAsync(ITechnicalSheetStorage storage, string storageKey, ILoggerFactory loggerFactory, CancellationToken ct)
    {
        try { await storage.DeleteAsync(storageKey, ct); }
        catch (Exception exception)
        {
            loggerFactory.CreateLogger(typeof(TechnicalSheetEndpoints)).LogWarning(exception, "Could not clean up a technical sheet file after a persistence failure.");
        }
    }
    private static string? ValidateName(string? name) => string.IsNullOrWhiteSpace(name) ? "El nombre es obligatorio." : name.Trim().Length > MaxNameLength ? $"El nombre no puede superar {MaxNameLength} caracteres." : null;
    private static string? ValidateFile(IFormFile? file)
    {
        if (file is null || file.Length == 0) return "Selecciona un archivo PDF con contenido.";
        if (file.Length > MaxFileSize) return "El PDF no puede superar 10 MB.";
        if (!string.Equals(Path.GetExtension(file.FileName), ".pdf", StringComparison.OrdinalIgnoreCase)) return "Solo se permiten archivos con extensión PDF.";
        if (!string.Equals(file.ContentType, "application/pdf", StringComparison.OrdinalIgnoreCase)) return "El archivo debe tener el tipo PDF.";
        if (Path.GetFileName(file.FileName).Length > 255) return "El nombre del archivo es demasiado largo.";
        return null;
    }

    private static TechnicalSheetResponse ToResponse(TechnicalSheet x) => new(x.Id, x.Name, x.OriginalFileName, x.ContentType, x.SizeBytes, x.CreatedAt, x.UpdatedAt, $"/technical-sheets/{x.Id}/file");
}
