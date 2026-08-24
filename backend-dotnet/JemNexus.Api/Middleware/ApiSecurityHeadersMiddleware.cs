namespace JemNexus.Api.Middleware;

public sealed class ApiSecurityHeadersMiddleware(RequestDelegate next)
{
    private const string ContentSecurityPolicy =
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'";

    public Task InvokeAsync(HttpContext context)
    {
        var includeContentSecurityPolicy = !context.Request.Path.StartsWithSegments("/swagger");

        context.Response.OnStarting(() =>
        {
            if (includeContentSecurityPolicy)
            {
                context.Response.Headers.TryAdd("Content-Security-Policy", ContentSecurityPolicy);
            }

            context.Response.Headers.TryAdd("X-Content-Type-Options", "nosniff");
            context.Response.Headers.TryAdd("X-Frame-Options", "DENY");
            context.Response.Headers.TryAdd("Referrer-Policy", "no-referrer");
            context.Response.Headers.TryAdd("Permissions-Policy", "camera=(), geolocation=(), microphone=()");
            context.Response.Headers.TryAdd("X-XSS-Protection", "0");
            context.Response.Headers.TryAdd("X-Permitted-Cross-Domain-Policies", "none");

            return Task.CompletedTask;
        });

        return next(context);
    }
}
