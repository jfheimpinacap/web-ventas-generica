using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Globalization;
using System.Threading.RateLimiting;
using JemNexus.Api.Contracts.Auth;
using JemNexus.Api.Data;
using JemNexus.Api.Endpoints;
using JemNexus.Api.Middleware;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using JemNexus.Api.Services.Notifications;
using JemNexus.Api.Services.ProductImages;
using JemNexus.Api.Services.TechnicalSheets;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http.Json;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

const string CorsPolicyName = "JemNexusFrontend";
const string AppName = "JEM Nexus API";

var builder = WebApplication.CreateBuilder(args);

JemNexusPdfFontResolver.EnsureConfigured();

builder.Configuration.AddEnvironmentVariables();
builder.WebHost.ConfigureKestrel(options => options.AddServerHeader = false);

builder.Services.AddHsts(options =>
{
    options.MaxAge = TimeSpan.FromDays(365);
    options.IncludeSubDomains = false;
    options.Preload = false;
});

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<CommercialQuoteIssueCoordinator>();
builder.Services.AddSingleton<ICommercialQuotePdfGenerator, CommercialQuotePdfGenerator>();

builder.Services.Configure<UploadOptions>(builder.Configuration.GetSection(UploadOptions.SectionName));
builder.Services.Configure<SeedUserOptions>(builder.Configuration.GetSection(SeedUserOptions.SectionName));
builder.Services.Configure<EmailOptions>(builder.Configuration.GetSection(EmailOptions.SectionName));
builder.Services.Configure<QuoteNotificationOptions>(builder.Configuration.GetSection(QuoteNotificationOptions.SectionName));
builder.Services.Configure<FrontendOptions>(builder.Configuration.GetSection(FrontendOptions.SectionName));

builder.Services.AddRateLimiter(options =>
{
    var rateLimitOptions = builder.Configuration.GetSection(JemNexusRateLimitOptions.SectionName).Get<JemNexusRateLimitOptions>()
        ?? throw new InvalidOperationException("RateLimiting configuration is required.");
    foreach (var (name, rule) in rateLimitOptions.RequiredRules())
    {
        if (rule is null || rule.PermitLimit <= 0 || rule.WindowSeconds <= 0)
        {
            throw new InvalidOperationException($"RateLimiting:{name} must define PermitLimit and WindowSeconds greater than zero.");
        }
    }

    var rateLimitingEnabled = rateLimitOptions.Enabled
        && (!builder.Environment.IsEnvironment("Test") || rateLimitOptions.EnableInTest);

    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    options.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(context =>
        CreateRateLimitPartition(context, context.User.Identity?.IsAuthenticated == true
            ? rateLimitOptions.GlobalAuthenticated!
            : rateLimitOptions.GlobalAnonymous!, rateLimitingEnabled));

    AddPolicy(options, RateLimitPolicies.AuthLogin, rateLimitOptions.AuthLogin!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.AuthSession, rateLimitOptions.AuthSession!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.PublicSubmission, rateLimitOptions.PublicSubmission!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.AuthenticatedWrite, rateLimitOptions.AuthenticatedWrite!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.Upload, rateLimitOptions.Upload!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.Download, rateLimitOptions.Download!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.NotificationTest, rateLimitOptions.NotificationTest!, rateLimitingEnabled);
    AddPolicy(options, RateLimitPolicies.QuoteIssue, rateLimitOptions.QuoteIssue!, rateLimitingEnabled);

    options.OnRejected = async (rejectedContext, cancellationToken) =>
    {
        if (rejectedContext.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retryAfter))
        {
            var seconds = Math.Max(1, (long)Math.Ceiling(retryAfter.TotalSeconds));
            rejectedContext.HttpContext.Response.Headers.RetryAfter = seconds.ToString(CultureInfo.InvariantCulture);
        }

        await Results.Problem(
            statusCode: StatusCodes.Status429TooManyRequests,
            title: "Demasiadas solicitudes.",
            detail: "Espera antes de intentarlo nuevamente.")
            .ExecuteAsync(rejectedContext.HttpContext);
    };
});

var jwtOptions = ResolveJwtOptions(builder.Configuration, builder.Environment);
builder.Services.Configure<JwtOptions>(options =>
{
    options.Issuer = jwtOptions.Issuer;
    options.Audience = jwtOptions.Audience;
    options.Secret = jwtOptions.Secret;
    options.AccessTokenMinutes = jwtOptions.AccessTokenMinutes;
    options.RefreshTokenDays = jwtOptions.RefreshTokenDays;
});

builder.Services.Configure<JsonOptions>(options =>
{
    // Django/DRF exposes snake_case fields today. Keep future ASP.NET Core responses aligned
    // unless DTOs explicitly override names with JsonPropertyName in later phases.
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    options.SerializerOptions.DictionaryKeyPolicy = JsonNamingPolicy.SnakeCaseLower;
});

builder.Services.Configure<Microsoft.AspNetCore.Mvc.JsonOptions>(options =>
{
    options.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    options.JsonSerializerOptions.DictionaryKeyPolicy = JsonNamingPolicy.SnakeCaseLower;
});

if (builder.Environment.IsProduction() && string.IsNullOrWhiteSpace(jwtOptions.Secret))
{
    throw new InvalidOperationException("Jwt:Secret or JWT_SECRET must be configured in Production.");
}

var signingSecret = string.IsNullOrWhiteSpace(jwtOptions.Secret)
    ? "development-placeholder-jwt-secret-configure-env-before-auth-use"
    : jwtOptions.Secret;

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.RequireHttpsMetadata = !builder.Environment.IsDevelopment() && !builder.Environment.IsEnvironment("Test");
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = jwtOptions.Issuer,
            ValidateAudience = true,
            ValidAudience = jwtOptions.Audience,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(signingSecret)),
            ValidateLifetime = true,
            ClockSkew = TimeSpan.FromMinutes(1),
            NameClaimType = ClaimTypes.Name,
            RoleClaimType = ClaimTypes.Role
        };
        options.Events = new JwtBearerEvents
        {
            OnTokenValidated = async context =>
            {
                var idValue = context.Principal?.FindFirstValue(ClaimTypes.NameIdentifier)
                    ?? context.Principal?.FindFirstValue("sub");
                var tokenRole = context.Principal?.FindFirstValue(ClaimTypes.Role)
                    ?? context.Principal?.FindFirstValue("role");
                var passwordVersion = context.Principal?.FindFirstValue("pwd_ver");
                if (!int.TryParse(idValue, out var userId) || string.IsNullOrEmpty(tokenRole) || string.IsNullOrEmpty(passwordVersion))
                {
                    context.Fail("Token invalidado.");
                    return;
                }

                var db = context.HttpContext.RequestServices.GetRequiredService<JemNexusDbContext>();
                var tokenService = context.HttpContext.RequestServices.GetRequiredService<IJwtTokenService>();
                var user = await db.AppUsers.AsNoTracking().FirstOrDefaultAsync(candidate => candidate.Id == userId, context.HttpContext.RequestAborted);
                if (user is null || !user.IsActive || !string.Equals(user.Role, tokenRole, StringComparison.Ordinal)
                    || !CryptographicOperations.FixedTimeEquals(
                        Encoding.UTF8.GetBytes(tokenService.GetPasswordVersion(user)),
                        Encoding.UTF8.GetBytes(passwordVersion)))
                {
                    context.Fail("Token invalidado.");
                }
            }
        };
    });

builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("RequireActiveUser", policy =>
        policy.RequireAuthenticatedUser()
            .RequireClaim("is_staff")
            .RequireAssertion(context => context.User.HasClaim("is_staff", "true") || context.User.HasClaim("is_superuser", "true")));

    options.AddPolicy("RequireSellerOrSupportAdmin", policy =>
        policy.RequireAuthenticatedUser()
            .RequireRole(AppRoles.Seller, AppRoles.SupportAdmin));

    options.AddPolicy("RequireSupportAdmin", policy =>
        policy.RequireAuthenticatedUser()
            .RequireRole(AppRoles.SupportAdmin));

    options.AddPolicy("RequireCommercialRead", policy =>
        policy.RequireAuthenticatedUser()
            .RequireAssertion(context =>
                context.User.IsInRole(AppRoles.Seller)
                || context.User.IsInRole(AppRoles.SupportAdmin)
                || context.User.HasClaim("is_staff", "true")
                || context.User.HasClaim("is_superuser", "true")));

    options.AddPolicy("RequireCommercialWrite", policy =>
        policy.RequireAuthenticatedUser()
            .RequireAssertion(context =>
                context.User.IsInRole(AppRoles.Seller)
                || context.User.IsInRole(AppRoles.SupportAdmin)
                || context.User.HasClaim("is_staff", "true")
                || context.User.HasClaim("is_superuser", "true")));
});

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddScoped<IPasswordHasher<AppUser>, PasswordHasher<AppUser>>();
builder.Services.AddScoped<IPasswordHasherService, PasswordHasherService>();
builder.Services.AddScoped<IJwtTokenService, JwtTokenService>();
builder.Services.AddScoped<ISellerCodeGenerator, SellerCodeGenerator>();
builder.Services.AddScoped<IQuoteNotificationService, SmtpQuoteNotificationService>();
builder.Services.AddSingleton<ITechnicalSheetStorage, LocalTechnicalSheetStorage>();
builder.Services.AddSingleton<IProductImageStorage, LocalProductImageStorage>();

var configuredConnection = builder.Configuration.GetConnectionString("DefaultConnection");
var defaultConnection = string.IsNullOrWhiteSpace(configuredConnection)
    ? "Server=(localdb)\\mssqllocaldb;Database=JemNexus_Local;Trusted_Connection=True;TrustServerCertificate=True"
    : configuredConnection;

builder.Services.AddDbContext<JemNexusDbContext>(options =>
    options.UseSqlServer(defaultConnection));

var allowedOrigins = GetAllowedOrigins(builder.Configuration);

builder.Services.AddCors(options =>
{
    options.AddPolicy(CorsPolicyName, policy =>
    {
        policy.WithOrigins(allowedOrigins)
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

var app = builder.Build();

app.UseMiddleware<ApiSecurityHeadersMiddleware>();

if (app.Environment.IsDevelopment() || app.Environment.IsEnvironment("QA"))
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler(exceptionApp =>
    {
        exceptionApp.Run(context =>
        {
            context.Response.StatusCode = StatusCodes.Status500InternalServerError;
            return Task.CompletedTask;
        });
    });
}

if (app.Environment.IsProduction())
{
    app.UseHsts();
}

if (!app.Environment.IsEnvironment("Test"))
{
    app.UseHttpsRedirection();
}

app.Use(NormalizeKnownTrailingSlashPaths);
app.UseRouting();
app.UseCors(CorsPolicyName);
app.UseAuthentication();
app.UseRateLimiter();
app.UseAuthorization();

IResult HealthResponse(IHostEnvironment environment)
{
    return Results.Ok(new
    {
        Status = "ok",
        App = AppName,
        Environment = environment.EnvironmentName,
        Timestamp = DateTimeOffset.UtcNow
    });
}

app.MapGet("/", (IHostEnvironment environment) => HealthResponse(environment))
    .WithName("RootHealth")
    .WithOpenApi();

app.MapGet("/health", (IHostEnvironment environment) => HealthResponse(environment))
    .WithName("Health")
    .WithOpenApi();

app.MapGet("/api/health", (IHostEnvironment environment) => HealthResponse(environment))
    .WithName("ApiHealth")
    .WithOpenApi();

MapAuthEndpoints(app);
app.MapPublicMediaEndpoints();
app.MapCommercialPublicReadEndpoints();
app.MapCommercialReadEndpoints();
app.MapCommercialWriteEndpoints();
app.MapTechnicalSheetEndpoints();
app.MapAdminUserEndpoints();
app.MapAdminCustomerEndpoints();
app.MapAdminCommercialQuoteEndpoints();

await SeedData.SeedUsersAsync(app.Services, app.Environment);

app.Run();

static Task NormalizeKnownTrailingSlashPaths(HttpContext context, Func<Task> next)
{
    var path = context.Request.Path;

    if ((path.StartsWithSegments("/api") || path.Equals("/health/", StringComparison.OrdinalIgnoreCase))
        && path.Value is { Length: > 1 } pathValue
        && pathValue.EndsWith('/'))
    {
        context.Request.Path = pathValue.TrimEnd('/');
    }

    return next();
}

static void MapAuthEndpoints(WebApplication app)
{
    app.MapPost("/api/auth/login", LoginAsync).AllowAnonymous().RequireRateLimiting(RateLimitPolicies.AuthLogin).WithName("AuthLogin").WithOpenApi();
    app.MapPost("/api/auth/refresh", RefreshAsync).AllowAnonymous().RequireRateLimiting(RateLimitPolicies.AuthSession).WithName("AuthRefresh").WithOpenApi();
    app.MapPost("/api/auth/logout", LogoutAsync).AllowAnonymous().RequireRateLimiting(RateLimitPolicies.AuthSession).WithName("AuthLogout").WithOpenApi();
    app.MapGet("/api/auth/me", MeAsync).RequireAuthorization().WithName("AuthMe").WithOpenApi();
}

static async Task<IResult> LoginAsync(
    LoginRequest request,
    JemNexusDbContext dbContext,
    IPasswordHasherService passwordHasher,
    IJwtTokenService jwtTokenService,
    CancellationToken cancellationToken)
{
    if (string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password))
    {
        return Results.Unauthorized();
    }

    var usernameOrEmail = request.Username.Trim();
    var user = await dbContext.AppUsers
        .FirstOrDefaultAsync(candidate => candidate.Username == usernameOrEmail || candidate.Email == usernameOrEmail, cancellationToken);

    if (user is null || !user.IsActive || !passwordHasher.VerifyPassword(user, request.Password))
    {
        return Results.Unauthorized();
    }

    var tokenPair = jwtTokenService.GenerateTokenPair(user);
    var refreshToken = new AppRefreshToken
    {
        UserId = user.Id,
        FamilyId = Guid.NewGuid(),
        TokenHash = jwtTokenService.HashRefreshToken(tokenPair.Refresh),
        PasswordVersion = jwtTokenService.GetPasswordVersion(user),
        ExpiresAt = tokenPair.RefreshExpiresAt
    };

    user.LastLoginAt = DateTimeOffset.UtcNow;
    dbContext.AppRefreshTokens.Add(refreshToken);
    await dbContext.SaveChangesAsync(cancellationToken);

    return Results.Ok(new LoginResponse(tokenPair.Access, tokenPair.Refresh, AuthUserResponse.FromUser(user)));
}

static async Task<IResult> RefreshAsync(
    RefreshRequest request,
    JemNexusDbContext dbContext,
    IJwtTokenService jwtTokenService,
    CancellationToken cancellationToken)
{
    if (string.IsNullOrWhiteSpace(request.Refresh))
    {
        return Results.Unauthorized();
    }

    var tokenHash = jwtTokenService.HashRefreshToken(request.Refresh);
    var refreshToken = await dbContext.AppRefreshTokens
        .Include(token => token.User)
        .FirstOrDefaultAsync(token => token.TokenHash == tokenHash, cancellationToken);

    if (refreshToken is null)
    {
        return Results.Unauthorized();
    }

    if (refreshToken.RevokedAt is not null)
    {
        if (refreshToken.ReplacedByTokenHash is not null)
        {
            await RevokeRefreshTokenFamilyAsync(dbContext, refreshToken.FamilyId, cancellationToken);
        }

        return Results.Unauthorized();
    }

    if (refreshToken.ExpiresAt <= DateTimeOffset.UtcNow || !refreshToken.User.IsActive)
    {
        return Results.Unauthorized();
    }

    var currentPasswordVersion = jwtTokenService.GetPasswordVersion(refreshToken.User);
    if (!PasswordVersionsMatch(refreshToken.PasswordVersion, currentPasswordVersion))
    {
        await RevokeRefreshTokenFamilyAsync(dbContext, refreshToken.FamilyId, cancellationToken);
        return Results.Unauthorized();
    }

    var tokenPair = jwtTokenService.GenerateTokenPair(refreshToken.User);
    var successorHash = jwtTokenService.HashRefreshToken(tokenPair.Refresh);
    refreshToken.RevokedAt = DateTimeOffset.UtcNow;
    refreshToken.ReplacedByTokenHash = successorHash;
    dbContext.AppRefreshTokens.Add(new AppRefreshToken
    {
        UserId = refreshToken.UserId,
        FamilyId = refreshToken.FamilyId,
        TokenHash = successorHash,
        PasswordVersion = currentPasswordVersion,
        ExpiresAt = tokenPair.RefreshExpiresAt
    });

    try
    {
        await dbContext.SaveChangesAsync(cancellationToken);
    }
    catch (DbUpdateConcurrencyException)
    {
        dbContext.ChangeTracker.Clear();
        var persistedToken = await dbContext.AppRefreshTokens
            .AsNoTracking()
            .FirstOrDefaultAsync(token => token.TokenHash == tokenHash, cancellationToken);
        if (persistedToken?.RevokedAt is not null && persistedToken.ReplacedByTokenHash is not null)
        {
            await RevokeRefreshTokenFamilyAsync(dbContext, persistedToken.FamilyId, cancellationToken);
        }

        return Results.Unauthorized();
    }

    return Results.Ok(new RefreshResponse(tokenPair.Access, tokenPair.Refresh));
}

static async Task<IResult> LogoutAsync(
    LogoutRequest request,
    JemNexusDbContext dbContext,
    IJwtTokenService jwtTokenService,
    CancellationToken cancellationToken)
{
    if (string.IsNullOrWhiteSpace(request.Refresh))
    {
        return Results.NoContent();
    }

    var tokenHash = jwtTokenService.HashRefreshToken(request.Refresh);
    var familyId = await dbContext.AppRefreshTokens
        .AsNoTracking()
        .Where(token => token.TokenHash == tokenHash)
        .Select(token => (Guid?)token.FamilyId)
        .FirstOrDefaultAsync(cancellationToken);
    if (familyId is not null)
    {
        await RevokeRefreshTokenFamilyAsync(dbContext, familyId.Value, cancellationToken);
    }

    return Results.NoContent();
}

static bool PasswordVersionsMatch(string? persistedVersion, string currentVersion)
{
    if (string.IsNullOrWhiteSpace(persistedVersion) || string.IsNullOrWhiteSpace(currentVersion))
    {
        return false;
    }

    var persistedBytes = Encoding.UTF8.GetBytes(persistedVersion);
    var currentBytes = Encoding.UTF8.GetBytes(currentVersion);
    return persistedBytes.Length == currentBytes.Length
        && CryptographicOperations.FixedTimeEquals(persistedBytes, currentBytes);
}

static async Task RevokeRefreshTokenFamilyAsync(
    JemNexusDbContext dbContext,
    Guid familyId,
    CancellationToken cancellationToken)
{
    const int maximumAttempts = 3;
    for (var attempt = 0; attempt < maximumAttempts; attempt++)
    {
        var activeTokens = await dbContext.AppRefreshTokens
            .Where(token => token.FamilyId == familyId && token.RevokedAt == null)
            .ToListAsync(cancellationToken);
        if (activeTokens.Count == 0)
        {
            return;
        }

        var revokedAt = DateTimeOffset.UtcNow;
        foreach (var token in activeTokens)
        {
            token.RevokedAt = revokedAt;
        }

        try
        {
            await dbContext.SaveChangesAsync(cancellationToken);
        }
        catch (DbUpdateConcurrencyException)
        {
            dbContext.ChangeTracker.Clear();
            if (attempt == maximumAttempts - 1)
            {
                var stillActive = await dbContext.AppRefreshTokens
                    .AsNoTracking()
                    .AnyAsync(token => token.FamilyId == familyId && token.RevokedAt == null, cancellationToken);
                if (stillActive)
                {
                    throw;
                }
            }
        }
    }
}

static async Task<IResult> MeAsync(ClaimsPrincipal principal, JemNexusDbContext dbContext, CancellationToken cancellationToken)
{
    var userIdValue = principal.FindFirstValue(ClaimTypes.NameIdentifier) ?? principal.FindFirstValue("sub");
    if (!int.TryParse(userIdValue, out var userId))
    {
        return Results.Unauthorized();
    }

    var user = await dbContext.AppUsers.FindAsync([userId], cancellationToken);
    if (user is null || !user.IsActive)
    {
        return Results.Unauthorized();
    }

    return Results.Ok(AuthUserResponse.FromUser(user));
}

static string[] GetAllowedOrigins(IConfiguration configuration)
{
    var configuredOrigins = configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? [];
    var environmentOrigins = configuration["FRONTEND_ORIGINS"]?
        .Split([',', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries) ?? [];

    return configuredOrigins
        .Concat(environmentOrigins)
        .Where(origin => !string.IsNullOrWhiteSpace(origin))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToArray();
}

static JwtOptions ResolveJwtOptions(IConfiguration configuration, IHostEnvironment environment)
{
    var options = configuration.GetSection(JwtOptions.SectionName).Get<JwtOptions>() ?? new JwtOptions();
    options.Secret = FirstNonEmpty(configuration["JWT_SECRET"], options.Secret);
    options.Issuer = FirstNonEmpty(configuration["JWT_ISSUER"], options.Issuer);
    options.Audience = FirstNonEmpty(configuration["JWT_AUDIENCE"], options.Audience);

    if (environment.IsEnvironment("Test") && string.IsNullOrWhiteSpace(options.Secret))
    {
        options.Secret = "test-only-jwt-secret-not-for-production-32chars";
    }

    return options;
}

static void AddPolicy(RateLimiterOptions options, string name, FixedWindowRateLimitRule rule, bool enabled)
{
    options.AddPolicy(name, context => CreateRateLimitPartition(context, rule, enabled));
}

static RateLimitPartition<string> CreateRateLimitPartition(HttpContext context, FixedWindowRateLimitRule rule, bool enabled)
{
    var key = GetRateLimitPartitionKey(context);
    return enabled
        ? RateLimitPartition.GetFixedWindowLimiter(key, _ => new FixedWindowRateLimiterOptions
        {
            PermitLimit = rule.PermitLimit,
            Window = TimeSpan.FromSeconds(rule.WindowSeconds),
            QueueLimit = 0,
            QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
            AutoReplenishment = true
        })
        : RateLimitPartition.GetNoLimiter(key);
}

static string GetRateLimitPartitionKey(HttpContext context)
{
    if (context.User.Identity?.IsAuthenticated == true)
    {
        var id = context.User.FindFirstValue(ClaimTypes.NameIdentifier)
            ?? context.User.FindFirstValue("sub")
            ?? context.User.Identity.Name;
        if (!string.IsNullOrWhiteSpace(id)) return $"user:{id}";
    }

    var address = context.Connection.RemoteIpAddress;
    if (address?.IsIPv4MappedToIPv6 == true) address = address.MapToIPv4();
    return $"ip:{address?.ToString() ?? "unknown"}";
}

static string FirstNonEmpty(params string?[] values)
{
    return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;
}

public partial class Program;
