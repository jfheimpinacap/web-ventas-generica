namespace JemNexus.Api.Models;

public static class AppRoles
{
    public const string Seller = "seller";
    // "Support" is the functional display name. Existing users persist this
    // historical identifier, which must remain stable for JWT authorization.
    public const string SupportAdmin = "support_admin";

    public static readonly ISet<string> All = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        Seller,
        SupportAdmin
    };
}
