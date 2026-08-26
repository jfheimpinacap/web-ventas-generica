namespace JemNexus.Api.Models;

public sealed class CustomerProfile
{
    public int Id { get; set; }
    public string BusinessName { get; set; } = string.Empty;
    public string Rut { get; set; } = string.Empty;
    public string NormalizedRut { get; set; } = string.Empty;
    public string BusinessActivity { get; set; } = string.Empty;
    public string Address { get; set; } = string.Empty;
    public string Phone { get; set; } = string.Empty;
    public string CityOrCommune { get; set; } = string.Empty;
    public string ContactName { get; set; } = string.Empty;
    public string? Email { get; set; }
    public string NormalizedBusinessName { get; set; } = string.Empty;
    public bool IsActive { get; set; } = true;
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public int? CreatedById { get; set; }
    public AppUser? CreatedBy { get; set; }
    public int? UpdatedById { get; set; }
    public AppUser? UpdatedBy { get; set; }
}
