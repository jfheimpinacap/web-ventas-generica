namespace JemNexus.Api.Dtos;

public sealed record TechnicalSheetResponse(int Id, string Name, string OriginalFileName, string ContentType, long SizeBytes, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt, string FileUrl);
public sealed record RenameTechnicalSheetRequest(string? Name);
