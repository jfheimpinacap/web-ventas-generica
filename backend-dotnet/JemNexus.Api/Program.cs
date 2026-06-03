using System.Text.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Options;
using Microsoft.AspNetCore.Http.Json;
using Microsoft.EntityFrameworkCore;

const string CorsPolicyName = "JemNexusFrontend";
const string AppName = "JEM Nexus API";

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddEnvironmentVariables();

builder.Services.Configure<UploadOptions>(builder.Configuration.GetSection(UploadOptions.SectionName));

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

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

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

app.UseCors(CorsPolicyName);

app.Use(async (context, next) =>
{
    if (context.Request.Path.Equals("/api/health/", StringComparison.OrdinalIgnoreCase))
    {
        context.Request.Path = "/api/health";
    }

    await next();
});

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

app.Run();

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

public partial class Program;
