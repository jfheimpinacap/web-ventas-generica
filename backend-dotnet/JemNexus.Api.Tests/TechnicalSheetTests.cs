using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using JemNexus.Api.Data;
using JemNexus.Api.Endpoints;
using JemNexus.Api.Models;
using JemNexus.Api.Services.TechnicalSheets;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed class TechnicalSheetTests : IDisposable
{
    private const string TestPassword = "DummyPassword123!";
    private readonly TechnicalSheetApiFactory _factory = new();

    public void Dispose() => _factory.Dispose();

    [Theory]
    [InlineData("GET", "/api/technical-sheets/")]
    [InlineData("GET", "/api/technical-sheets/1/")]
    [InlineData("POST", "/api/technical-sheets/")]
    [InlineData("PATCH", "/api/technical-sheets/1/")]
    [InlineData("POST", "/api/technical-sheets/1/file/")]
    [InlineData("GET", "/api/technical-sheets/1/file/")]
    [InlineData("GET", "/api/technical-sheets/1/file/?download=true")]
    [InlineData("DELETE", "/api/technical-sheets/1/")]
    public async Task EveryTechnicalSheetOperationRequiresAuthentication(string method, string path)
    {
        using var client = _factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        request.Content = (method, path) switch
        {
            ("PATCH", _) => JsonContent.Create(new { name = "Ficha" }),
            ("POST", "/api/technical-sheets/") => PdfForm("Ficha", "valid.pdf", "%PDF"u8.ToArray()),
            ("POST", _) => PdfOnlyForm("valid.pdf", "%PDF"u8.ToArray()),
            _ => null
        };
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }

    [Fact]
    public async Task SellerCreatesPdfAndContractHidesInternalStorageDetails()
    {
        using var client = await CreateAuthorizedClientAsync();
        var response = await client.PostAsync("/api/technical-sheets/", PdfForm("  Ficha Genie  ", "customer/path/genie.pdf", "%PDF-demo"u8.ToArray()));
        var payload = await ReadJsonAsync<JsonElement>(response);

        Assert.Equal("Ficha Genie", payload.GetProperty("name").GetString());
        Assert.Equal("genie.pdf", payload.GetProperty("original_file_name").GetString());
        Assert.Equal("application/pdf", payload.GetProperty("content_type").GetString());
        Assert.Equal(9, payload.GetProperty("size_bytes").GetInt64());
        AssertContractHidesStorage(payload);

        using var scope = _factory.Services.CreateScope();
        var entity = await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().TechnicalSheets.SingleAsync();
        Assert.Matches("^[a-f0-9]{32}\\.pdf$", entity.StorageKey);
        Assert.DoesNotContain("genie", entity.StorageKey, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain('/', entity.StorageKey);
        Assert.True(_factory.Storage.Exists(entity.StorageKey));

        AssertContractHidesStorage(await ReadJsonAsync<JsonElement>(await client.GetAsync($"/api/technical-sheets/{entity.Id}/")));
        Assert.All((await ReadJsonAsync<JsonElement[]>(await client.GetAsync("/api/technical-sheets/"))), AssertContractHidesStorage);
    }

    [Theory]
    [InlineData("empty", "valid.pdf", "application/pdf", 0)]
    [InlineData("extension", "invalid.txt", "application/pdf", 4)]
    [InlineData("mime", "valid.pdf", "text/plain", 4)]
    public async Task InvalidPdfIsRejected(string _, string fileName, string contentType, long length)
    {
        using var client = await CreateAuthorizedClientAsync();
        using var content = PdfForm("Ficha", fileName, new byte[checked((int)length)], contentType);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/technical-sheets/", content)).StatusCode);
        Assert.Empty(_factory.Storage.Keys);
    }

    [Fact]
    public async Task PdfLargerThanTenMegabytesIsRejected()
    {
        using var client = await CreateAuthorizedClientAsync();
        var bytes = new byte[checked((int)TechnicalSheetEndpoints.MaxFileSize + 1)];
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/technical-sheets/", PdfForm("Ficha", "large.pdf", bytes))).StatusCode);
        Assert.Empty(_factory.Storage.Keys);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task EmptyNameIsRejected(string name)
    {
        using var client = await CreateAuthorizedClientAsync();
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/technical-sheets/", PdfForm(name, "valid.pdf", "%PDF"u8.ToArray()))).StatusCode);
    }

    [Fact]
    public async Task ExcessiveVisibleAndOriginalNamesAreRejected()
    {
        using var client = await CreateAuthorizedClientAsync();
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/technical-sheets/", PdfForm(new string('n', TechnicalSheetEndpoints.MaxNameLength + 1), "valid.pdf", "%PDF"u8.ToArray()))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync("/api/technical-sheets/", PdfForm("Ficha", new string('f', 252) + ".pdf", "%PDF"u8.ToArray()))).StatusCode);
    }

    [Fact]
    public async Task SearchFindsNamesCaseInsensitively()
    {
        using var client = await CreateAuthorizedClientAsync();
        await CreateAsync(client, "Ficha Genie", "genie.pdf", "%PDF-a"u8.ToArray());
        await CreateAsync(client, "Manual Toyota", "toyota.pdf", "%PDF-b"u8.ToArray());
        var items = await ReadJsonAsync<JsonElement[]>(await client.GetAsync("/api/technical-sheets/?search=Genie"));
        Assert.Single(items);
        Assert.Equal("Ficha Genie", items[0].GetProperty("name").GetString());
    }

    [Theory]
    [InlineData("GET", "/api/technical-sheets/999/")]
    [InlineData("PATCH", "/api/technical-sheets/999/")]
    [InlineData("POST", "/api/technical-sheets/999/file/")]
    [InlineData("GET", "/api/technical-sheets/999/file/")]
    [InlineData("DELETE", "/api/technical-sheets/999/")]
    public async Task MissingIdentifierReturnsNotFound(string method, string path)
    {
        using var client = await CreateAuthorizedClientAsync();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        request.Content = method == "PATCH" ? JsonContent.Create(new { name = "Nueva" }) : method == "POST" ? PdfOnlyForm("valid.pdf", "%PDF"u8.ToArray()) : null;
        Assert.Equal(HttpStatusCode.NotFound, (await client.SendAsync(request)).StatusCode);
    }

    [Fact]
    public async Task RenameOnlyChangesNameAndKeepsPdf()
    {
        using var client = await CreateAuthorizedClientAsync();
        var created = await CreateAsync(client, "Anterior", "original.pdf", "%PDF-original"u8.ToArray());
        var before = await GetEntityAsync(created.GetProperty("id").GetInt32());
        var response = await client.PatchAsJsonAsync($"/api/technical-sheets/{before.Id}/", new { name = "  Nuevo  " });
        var renamed = await ReadJsonAsync<JsonElement>(response);
        var after = await GetEntityAsync(before.Id);
        Assert.Equal("Nuevo", renamed.GetProperty("name").GetString());
        Assert.Equal(before.StorageKey, after.StorageKey);
        Assert.Equal(before.OriginalFileName, after.OriginalFileName);
        Assert.Equal(before.ContentType, after.ContentType);
        Assert.Equal(before.SizeBytes, after.SizeBytes);
        Assert.True(_factory.Storage.Exists(before.StorageKey));
        Assert.True(after.UpdatedAt >= before.UpdatedAt);
    }

    [Fact]
    public async Task ValidReplacementUpdatesMetadataAndDeletesOldFile()
    {
        using var client = await CreateAuthorizedClientAsync();
        var created = await CreateAsync(client, "Ficha", "old.pdf", "%PDF-old"u8.ToArray());
        var before = await GetEntityAsync(created.GetProperty("id").GetInt32());
        var response = await client.PostAsync($"/api/technical-sheets/{before.Id}/file/", PdfOnlyForm("new.pdf", "%PDF-new-document"u8.ToArray()));
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var after = await GetEntityAsync(before.Id);
        Assert.Equal("new.pdf", after.OriginalFileName);
        Assert.Equal("application/pdf", after.ContentType);
        Assert.Equal(17, after.SizeBytes);
        Assert.NotEqual(before.StorageKey, after.StorageKey);
        Assert.False(_factory.Storage.Exists(before.StorageKey));
        Assert.True(_factory.Storage.Exists(after.StorageKey));
    }

    [Fact]
    public async Task InvalidReplacementKeepsOldRecordAndFileWithoutOrphan()
    {
        using var client = await CreateAuthorizedClientAsync();
        var created = await CreateAsync(client, "Ficha", "old.pdf", "%PDF-old"u8.ToArray());
        var before = await GetEntityAsync(created.GetProperty("id").GetInt32());
        var keysBefore = _factory.Storage.Keys.ToArray();
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync($"/api/technical-sheets/{before.Id}/file/", PdfOnlyForm("bad.txt", "bad"u8.ToArray(), "text/plain"))).StatusCode);
        var after = await GetEntityAsync(before.Id);
        Assert.Equal(before.StorageKey, after.StorageKey);
        Assert.Equal(before.OriginalFileName, after.OriginalFileName);
        Assert.Equal(keysBefore, _factory.Storage.Keys);
        Assert.True(_factory.Storage.Exists(before.StorageKey));
    }

    [Fact]
    public async Task PersistenceFailureCleansNewFilesAndPreservesReplacementState()
    {
        using var client = await CreateAuthorizedClientAsync();
        var created = await CreateAsync(client, "Ficha", "old.pdf", "%PDF-old"u8.ToArray());
        var before = await GetEntityAsync(created.GetProperty("id").GetInt32());
        _factory.PersistenceFailure.FailNextSave();

        var replacement = await client.PostAsync($"/api/technical-sheets/{before.Id}/file/", PdfOnlyForm("new.pdf", "%PDF-new"u8.ToArray()));
        Assert.Equal(HttpStatusCode.InternalServerError, replacement.StatusCode);
        await AssertSafePersistenceFailureAsync(replacement);
        var after = await GetEntityAsync(before.Id);
        Assert.Equal(before.Id, after.Id);
        Assert.Equal(before.StorageKey, after.StorageKey);
        Assert.Equal(before.OriginalFileName, after.OriginalFileName);
        Assert.Equal(before.ContentType, after.ContentType);
        Assert.Equal(before.SizeBytes, after.SizeBytes);
        Assert.Equal(before.UpdatedAt, after.UpdatedAt);
        Assert.Single(_factory.Storage.Keys);
        Assert.True(_factory.Storage.Exists(before.StorageKey));

        _factory.PersistenceFailure.FailNextSave();
        var creation = await client.PostAsync("/api/technical-sheets/", PdfForm("Otra", "other.pdf", "%PDF-other"u8.ToArray()));
        Assert.Equal(HttpStatusCode.InternalServerError, creation.StatusCode);
        await AssertSafePersistenceFailureAsync(creation);
        Assert.Single(_factory.Storage.Keys);
        using var scope = _factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
        Assert.Single(await db.TechnicalSheets.AsNoTracking().ToListAsync());
        Assert.False(db.ChangeTracker.HasChanges());
    }

    [Fact]
    public async Task FileEndpointUsesInlineAndAttachmentHeaders()
    {
        using var client = await CreateAuthorizedClientAsync();
        var item = await CreateAsync(client, "Ficha", "safe-name.pdf", "%PDF-content"u8.ToArray());
        var id = item.GetProperty("id").GetInt32();
        var inline = await client.GetAsync($"/api/technical-sheets/{id}/file/");
        var attachment = await client.GetAsync($"/api/technical-sheets/{id}/file/?download=true");
        Assert.Equal("application/pdf", inline.Content.Headers.ContentType?.MediaType);
        Assert.Null(inline.Content.Headers.ContentDisposition);
        Assert.Equal("attachment", attachment.Content.Headers.ContentDisposition?.DispositionType);
        Assert.Equal("safe-name.pdf", attachment.Content.Headers.ContentDisposition?.FileNameStar);
    }

    [Fact]
    public async Task DeleteRemovesOnlyAssociatedPdfAndRecord()
    {
        using var client = await CreateAuthorizedClientAsync();
        var first = await CreateAsync(client, "Primera", "first.pdf", "%PDF-first"u8.ToArray());
        var second = await CreateAsync(client, "Segunda", "second.pdf", "%PDF-second"u8.ToArray());
        var firstEntity = await GetEntityAsync(first.GetProperty("id").GetInt32());
        var secondEntity = await GetEntityAsync(second.GetProperty("id").GetInt32());
        var unrelatedKey = _factory.Storage.AddUnrelated("images/product.jpg", "image"u8.ToArray());
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/technical-sheets/{firstEntity.Id}/")).StatusCode);
        Assert.False(_factory.Storage.Exists(firstEntity.StorageKey));
        Assert.True(_factory.Storage.Exists(secondEntity.StorageKey));
        Assert.True(_factory.Storage.Exists(unrelatedKey));
        using var scope = _factory.Services.CreateScope();
        Assert.False(await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().TechnicalSheets.AnyAsync(x => x.Id == firstEntity.Id));
    }

    [Fact]
    public async Task LocalStorageUsesCreateNewOpaqueNamesAndRejectsTraversal()
    {
        var root = Path.Combine(Path.GetTempPath(), $"jem-technical-sheets-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var storage = new LocalTechnicalSheetStorage(new TestEnvironment(root));
            await using var first = new MemoryStream("%PDF-first"u8.ToArray());
            await using var second = new MemoryStream("%PDF-second"u8.ToArray());
            var firstKey = await storage.SaveAsync(first, default);
            var secondKey = await storage.SaveAsync(second, default);
            Assert.Matches("^[a-f0-9]{32}\\.pdf$", firstKey);
            Assert.NotEqual(firstKey, secondKey);
            Assert.True(File.Exists(Path.Combine(root, "uploads", "technical-sheets", firstKey)));
            await Assert.ThrowsAsync<InvalidOperationException>(() => storage.DeleteAsync("../outside.pdf", default));
            await Assert.ThrowsAsync<InvalidOperationException>(() => storage.OpenReadAsync("folder/file.pdf", default));
        }
        finally { Directory.Delete(root, true); }
    }

    [Fact]
    public void EntityModelSupportsInMemoryAndHasNoPhysicalPathContract()
    {
        using var db = new JemNexusDbContext(InMemoryTestDatabase.CreateOptions(InMemoryTestDatabase.CreateDatabaseName("technical-sheets")));
        var entity = db.Model.FindEntityType(typeof(TechnicalSheet))!;
        Assert.Equal("TechnicalSheets", entity.GetTableName());
        Assert.Null(entity.FindProperty("PhysicalPath"));
    }

    private async Task<HttpClient> CreateAuthorizedClientAsync()
    {
        var client = _factory.CreateClient();
        var login = await ReadJsonAsync<LoginPayload>(await client.PostAsJsonAsync("/api/auth/login/", new { username = "demo", password = TestPassword }));
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", login.Access);
        return client;
    }

    private static MultipartFormDataContent PdfForm(string name, string fileName, byte[] bytes, string contentType = "application/pdf") => PdfForm(name, fileName, new ByteArrayContent(bytes), contentType);
    private static MultipartFormDataContent PdfForm(string name, string fileName, HttpContent file, string contentType)
    {
        var form = PdfOnlyForm(fileName, file, contentType); form.Add(new StringContent(name), "name"); return form;
    }
    private static MultipartFormDataContent PdfOnlyForm(string fileName, byte[] bytes, string contentType = "application/pdf") => PdfOnlyForm(fileName, new ByteArrayContent(bytes), contentType);
    private static MultipartFormDataContent PdfOnlyForm(string fileName, HttpContent file, string contentType)
    {
        file.Headers.ContentType = new MediaTypeHeaderValue(contentType);
        var form = new MultipartFormDataContent(); form.Add(file, "file", fileName); return form;
    }
    private static async Task<JsonElement> CreateAsync(HttpClient client, string name, string fileName, byte[] bytes) => await ReadJsonAsync<JsonElement>(await client.PostAsync("/api/technical-sheets/", PdfForm(name, fileName, bytes)));
    private async Task<TechnicalSheet> GetEntityAsync(int id)
    {
        using var scope = _factory.Services.CreateScope();
        return await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().TechnicalSheets.AsNoTracking().SingleAsync(x => x.Id == id);
    }
    private static void AssertContractHidesStorage(JsonElement value)
    {
        var json = value.GetRawText();
        Assert.DoesNotContain("storage_key", json, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("uploads", json, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("ContentRootPath", json, StringComparison.OrdinalIgnoreCase);
    }
    private static async Task AssertSafePersistenceFailureAsync(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("Simulated technical sheet persistence failure", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("storage", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("uploads", body, StringComparison.OrdinalIgnoreCase);
    }
    private static async Task<T> ReadJsonAsync<T>(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(response.IsSuccessStatusCode, $"Status: {response.StatusCode}, Body: {body}");
        return (await response.Content.ReadFromJsonAsync<T>())!;
    }

    public sealed class TechnicalSheetApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _databaseName = InMemoryTestDatabase.CreateDatabaseName("TechnicalSheetTests");
        private readonly InMemoryDatabaseRoot _databaseRoot = InMemoryTestDatabase.CreateDatabaseRoot();
        public FakeTechnicalSheetStorage Storage { get; } = new();
        public TechnicalSheetPersistenceFailureInterceptor PersistenceFailure { get; } = new();
        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Test");
            builder.ConfigureAppConfiguration((_, configuration) => configuration.AddInMemoryCollection(TestConfiguration));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<JemNexusDbContext>>();
                services.RemoveAll<ITechnicalSheetStorage>();
                services.AddDbContext<JemNexusDbContext>(options =>
                {
                    InMemoryTestDatabase.Configure(options, _databaseName, _databaseRoot);
                    options.AddInterceptors(PersistenceFailure);
                });
                services.AddSingleton<ITechnicalSheetStorage>(Storage);
            });
        }
    }

    public sealed class TechnicalSheetPersistenceFailureInterceptor : SaveChangesInterceptor
    {
        private int _failuresRemaining;
        public void FailNextSave() => Interlocked.Exchange(ref _failuresRemaining, 1);
        public override ValueTask<InterceptionResult<int>> SavingChangesAsync(DbContextEventData eventData, InterceptionResult<int> result, CancellationToken cancellationToken = default)
        {
            if (eventData.Context?.ChangeTracker.Entries<TechnicalSheet>().Any(entry => entry.State is EntityState.Added or EntityState.Modified) == true
                && Interlocked.CompareExchange(ref _failuresRemaining, 0, 1) == 1)
                throw new DbUpdateException("Simulated technical sheet persistence failure.");
            return base.SavingChangesAsync(eventData, result, cancellationToken);
        }
    }

    public sealed class FakeTechnicalSheetStorage : ITechnicalSheetStorage
    {
        private readonly Dictionary<string, byte[]> _files = [];
        public IEnumerable<string> Keys => _files.Keys.Order();
        public bool Exists(string key) => _files.ContainsKey(key);
        public string AddUnrelated(string key, byte[] bytes) { _files[key] = bytes; return key; }
        public async Task<string> SaveAsync(Stream content, CancellationToken cancellationToken)
        {
            var key = $"{Guid.NewGuid():N}.pdf"; using var memory = new MemoryStream(); await content.CopyToAsync(memory, cancellationToken); _files.Add(key, memory.ToArray()); return key;
        }
        public Task<Stream?> OpenReadAsync(string key, CancellationToken cancellationToken) => Task.FromResult<Stream?>(_files.TryGetValue(key, out var bytes) ? new MemoryStream(bytes) : null);
        public Task DeleteAsync(string key, CancellationToken cancellationToken) { _files.Remove(key); return Task.CompletedTask; }
    }

    private sealed class TestEnvironment(string root) : Microsoft.Extensions.Hosting.IHostEnvironment
    {
        public string EnvironmentName { get; set; } = "Test"; public string ApplicationName { get; set; } = "Tests"; public string ContentRootPath { get; set; } = root; public Microsoft.Extensions.FileProviders.IFileProvider ContentRootFileProvider { get; set; } = null!;
    }
    private static readonly IReadOnlyDictionary<string, string?> TestConfiguration = new Dictionary<string, string?>
    {
        ["Jwt:Issuer"] = "JEM Nexus API Test", ["Jwt:Audience"] = "JEM Nexus Frontend Test", ["JWT_SECRET"] = "DummyJwtSecretForTests1234567890!",
        ["SeedUsers:SellerUsername"] = "demo", ["SeedUsers:SellerPassword"] = TestPassword, ["SeedUsers:SellerEmail"] = "demo@example.test"
    };
    private sealed record LoginPayload(string Access, string Refresh, [property: JsonPropertyName("user")] JsonElement User);
}
