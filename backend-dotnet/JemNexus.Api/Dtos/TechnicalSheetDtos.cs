namespace JemNexus.Api.Dtos;

public sealed record TechnicalSheetResponse(int Id, string Name, string OriginalFileName, string ContentType, long SizeBytes, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt, string FileUrl);
public sealed record RenameTechnicalSheetRequest(string? Name);

public static class TechnicalSheetDtoMapper
{
    public static TechnicalSheetResponse ToResponse(JemNexus.Api.Models.TechnicalSheet sheet) =>
        new(sheet.Id, sheet.Name, sheet.OriginalFileName, sheet.ContentType, sheet.SizeBytes, sheet.CreatedAt, sheet.UpdatedAt, $"/technical-sheets/{sheet.Id}/file");
}
