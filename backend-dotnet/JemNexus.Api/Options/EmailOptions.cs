namespace JemNexus.Api.Options;

public sealed class EmailOptions
{
    public const string SectionName = "Email";
    public string SmtpHost { get; set; } = string.Empty;
    public int SmtpPort { get; set; } = 587;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public string FromAddress { get; set; } = string.Empty;
    public string FromName { get; set; } = string.Empty;
    public bool UseSsl { get; set; } = true;
    public string Security { get; set; } = string.Empty;
    public int TimeoutSeconds { get; set; } = 10;

    public string ResolveSecurityMode()
    {
        if (EmailSecurityModes.IsSupported(Security)) return EmailSecurityModes.Normalize(Security);
        return SmtpPort switch
        {
            465 => EmailSecurityModes.SslOnConnect,
            587 => EmailSecurityModes.StartTls,
            _ when UseSsl => EmailSecurityModes.Auto,
            _ => EmailSecurityModes.None
        };
    }
}
