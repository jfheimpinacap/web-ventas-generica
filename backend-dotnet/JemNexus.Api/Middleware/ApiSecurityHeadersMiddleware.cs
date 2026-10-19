namespace JemNexus.Api.Middleware;

public sealed class ApiSecurityHeadersMiddleware(RequestDelegate next, IHostEnvironment environment)
{
    private const string ContentSecurityPolicy =
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'";
    private static readonly object PublicInlinePdfKey = new();
    private readonly string _publicInlinePdfPolicy =
        "default-src 'none'; base-uri 'none'; frame-ancestors https://jem-nexus.cl https://www.jem-nexus.cl"
        + (environment.IsDevelopment() ? " http://localhost:5174 http://127.0.0.1:5174" : "")
        + "; form-action 'none'";

    // Only the public endpoint may opt in, after checking publication, PDF type and physical file.
    internal static void AllowPublicInlinePdf(HttpContext context) => context.Items[PublicInlinePdfKey] = true;

    public Task InvokeAsync(HttpContext context)
    {
        var includeContentSecurityPolicy = !context.Request.Path.StartsWithSegments("/swagger");

        context.Response.OnStarting(() =>
        {
            var allowPublicInlinePdf = context.Items.ContainsKey(PublicInlinePdfKey)
                && context.Response.StatusCode is StatusCodes.Status200OK or StatusCodes.Status206PartialContent;
            if (includeContentSecurityPolicy)
            {
                context.Response.Headers.TryAdd("Content-Security-Policy", allowPublicInlinePdf ? _publicInlinePdfPolicy : ContentSecurityPolicy);
            }

            context.Response.Headers.TryAdd("X-Content-Type-Options", "nosniff");
            if (!allowPublicInlinePdf) context.Response.Headers.TryAdd("X-Frame-Options", "DENY");
            context.Response.Headers.TryAdd("Referrer-Policy", "no-referrer");
            context.Response.Headers.TryAdd("Permissions-Policy", "camera=(), geolocation=(), microphone=()");
            context.Response.Headers.TryAdd("X-XSS-Protection", "0");
            context.Response.Headers.TryAdd("X-Permitted-Cross-Domain-Policies", "none");

            return Task.CompletedTask;
        });

        return next(context);
    }
}
