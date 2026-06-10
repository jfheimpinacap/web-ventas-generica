namespace JemNexus.Api.Options;

public sealed class SeedUserOptions
{
    public const string SectionName = "SeedUsers";

    public string SellerUsername { get; set; } = "demo";
    public string SellerPassword { get; set; } = string.Empty;
    public string SellerEmail { get; set; } = string.Empty;
    public string SellerFullName { get; set; } = "Vendedor Demo";
    public string SupportUsername { get; set; } = "support";
    public string SupportPassword { get; set; } = string.Empty;
    public string SupportEmail { get; set; } = string.Empty;
    public string SupportFullName { get; set; } = "Administrador Soporte";
    public bool UpdateExistingPasswords { get; set; }
}
