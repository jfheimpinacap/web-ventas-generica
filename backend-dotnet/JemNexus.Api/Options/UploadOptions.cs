namespace JemNexus.Api.Options;

public sealed class UploadOptions
{
    public const string SectionName = "Uploads";

    public string RootPath { get; set; } = string.Empty;
    public string PublicBasePath { get; set; } = "/media";
    public string[] AllowedExtensions { get; set; } = [".jpg", ".jpeg", ".png", ".webp"];
    public int MaxFileSizeMb { get; set; } = 5;
}
