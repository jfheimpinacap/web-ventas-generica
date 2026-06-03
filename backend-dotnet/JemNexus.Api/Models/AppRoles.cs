namespace JemNexus.Api.Models;

public static class AppRoles
{
    public const string Seller = "seller";
    public const string SupportAdmin = "support_admin";

    public static readonly ISet<string> All = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        Seller,
        SupportAdmin
    };
}
