using System.Text.Json;
using Microsoft.AspNetCore.Http.Json;

const string CorsPolicyName = "JemNexusFrontend";
const string AppName = "JEM Nexus API";

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddEnvironmentVariables();

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

app.UseHttpsRedirection();
app.UseCors(CorsPolicyName);

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

app.MapGet("/api/health/", (IHostEnvironment environment) => HealthResponse(environment))
    .WithName("ApiHealthTrailingSlash")
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
