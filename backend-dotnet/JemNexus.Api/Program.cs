using System.Security.Claims;
using System.Text;
using System.Text.Json;
using JemNexus.Api.Contracts.Auth;
using JemNexus.Api.Data;
using JemNexus.Api.Endpoints;
using JemNexus.Api.Models;
using JemNexus.Api.Options;
using JemNexus.Api.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http.Json;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

const string CorsPolicyName = "JemNexusFrontend";
const string AppName = "JEM Nexus API";

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddEnvironmentVariables();

builder.Services.Configure<UploadOptions>(builder.Configuration.GetSection(UploadOptions.SectionName));
builder.Services.Configure<SeedUserOptions>(builder.Configuration.GetSection(SeedUserOptions.SectionName));

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

if (app.Environment.IsDevelopment() || app.Environment.IsEnvironment("QA"))
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

if (!app.Environment.IsEnvironment("Test"))
{
    app.UseHttpsRedirection();
}

app.Use(NormalizeKnownTrailingSlashPaths);
app.UseRouting();
app.UseCors(CorsPolicyName);
app.UseAuthentication();
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
app.MapCommercialReadEndpoints();
app.MapCommercialWriteEndpoints();

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
    app.MapPost("/api/auth/login", LoginAsync).AllowAnonymous().WithName("AuthLogin").WithOpenApi();
    app.MapPost("/api/auth/refresh", RefreshAsync).AllowAnonymous().WithName("AuthRefresh").WithOpenApi();
    app.MapGet("/api/auth/me", MeAsync).RequireAuthorization().WithName("AuthMe").WithOpenApi();
}

static async Task<IResult> LoginAsync(
    LoginRequest request,
    JemNexusDbContext dbContext,
    IPasswordHasherService passwordHasher,
    IJwtTokenService jwtTokenService,
    Microsoft.Extensions.Options.IOptions<JwtOptions> jwtOptions,
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
        TokenHash = jwtTokenService.HashRefreshToken(tokenPair.Refresh),
        ExpiresAt = DateTimeOffset.UtcNow.AddDays(jwtOptions.Value.RefreshTokenDays)
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

    if (refreshToken is null || refreshToken.RevokedAt is not null || refreshToken.ExpiresAt <= DateTimeOffset.UtcNow || !refreshToken.User.IsActive)
    {
        return Results.Unauthorized();
    }

    var access = jwtTokenService.GenerateAccessToken(refreshToken.User);
    return Results.Ok(new RefreshResponse(access));
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

static string FirstNonEmpty(params string?[] values)
{
    return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;
}

public partial class Program;
