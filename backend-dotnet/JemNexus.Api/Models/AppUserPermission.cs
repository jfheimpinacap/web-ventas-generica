namespace JemNexus.Api.Models;

public sealed class AppUserPermission
{
    public int UserId { get; set; }
    public string Permission { get; set; } = string.Empty;
    public AppUser User { get; set; } = null!;
}
