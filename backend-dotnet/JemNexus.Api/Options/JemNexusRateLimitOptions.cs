namespace JemNexus.Api.Options;

public sealed class JemNexusRateLimitOptions
{
    public const string SectionName = "RateLimiting";

    public bool Enabled { get; set; } = true;
    public bool EnableInTest { get; set; }
    public FixedWindowRateLimitRule? GlobalAnonymous { get; set; }
    public FixedWindowRateLimitRule? GlobalAuthenticated { get; set; }
    public FixedWindowRateLimitRule? AuthLogin { get; set; }
    public FixedWindowRateLimitRule? AuthSession { get; set; }
    public FixedWindowRateLimitRule? PublicSubmission { get; set; }
    public FixedWindowRateLimitRule? AuthenticatedWrite { get; set; }
    public FixedWindowRateLimitRule? Upload { get; set; }
    public FixedWindowRateLimitRule? Download { get; set; }
    public FixedWindowRateLimitRule? NotificationTest { get; set; }
    public FixedWindowRateLimitRule? QuoteIssue { get; set; }

    public IEnumerable<(string Name, FixedWindowRateLimitRule? Rule)> RequiredRules()
    {
        yield return (nameof(GlobalAnonymous), GlobalAnonymous);
        yield return (nameof(GlobalAuthenticated), GlobalAuthenticated);
        yield return (nameof(AuthLogin), AuthLogin);
        yield return (nameof(AuthSession), AuthSession);
        yield return (nameof(PublicSubmission), PublicSubmission);
        yield return (nameof(AuthenticatedWrite), AuthenticatedWrite);
        yield return (nameof(Upload), Upload);
        yield return (nameof(Download), Download);
        yield return (nameof(NotificationTest), NotificationTest);
        yield return (nameof(QuoteIssue), QuoteIssue);
    }
}

public sealed class FixedWindowRateLimitRule
{
    public int PermitLimit { get; set; }
    public int WindowSeconds { get; set; }
}

public static class RateLimitPolicies
{
    public const string AuthLogin = "auth-login";
    public const string AuthSession = "auth-session";
    public const string PublicSubmission = "public-submission";
    public const string AuthenticatedWrite = "authenticated-write";
    public const string Upload = "upload";
    public const string Download = "download";
    public const string NotificationTest = "notification-test";
    public const string QuoteIssue = "quote-issue";
}
