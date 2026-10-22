using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using JemNexus.Api.Data;
using JemNexus.Api.Models;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using JemNexus.Api.Services.Notifications;
using Xunit;

namespace JemNexus.Api.Tests;

public sealed partial class CommercialWriteEndpointTests
{
    private static Dictionary<string, object?> RentalPayload() => new()
    {
        ["name"] = "Modelo arriendo prueba aislada", ["category"] = 1, ["brand"] = 1, ["supplier"] = 1,
        ["product_type"] = "machinery", ["commercial_mode"] = "rental",
        ["rental_price_day"] = 18999, ["rental_price_week"] = 250000, ["rental_price_month"] = 650000,
        ["price_currency"] = "CLP", ["price_tax_mode"] = "plus_vat", ["price_visible"] = true,
        ["is_published"] = true, ["is_featured"] = true,
        ["platform_height_m"] = 12.5m, ["working_height_m"] = 14.5m, ["machine_weight_kg"] = 6200m,
        ["model"] = "Z-45", ["maximum_load_capacity_kg"] = 230m, ["power_source"] = "diesel",
        ["rental_includes_technical_advice"] = true, ["rental_includes_onsite_service"] = true,
        ["rental_includes_transport_coordination"] = true
    };

    [Fact]
    public async Task RentalCanBeCreatedEditedAndReloadedWithoutConditionOrStock()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", RentalPayload()));
        var id = created.GetProperty("id").GetInt32();
        var slug = created.GetProperty("slug").GetString();
        Assert.Equal("rental", created.GetProperty("commercial_mode").GetString());
        Assert.Equal("not_applicable", created.GetProperty("condition").GetString());
        Assert.Equal("on_request", created.GetProperty("stock_status").GetString());
        Assert.Equal(JsonValueKind.Null, created.GetProperty("price").ValueKind);
        Assert.Equal(JsonValueKind.Null, created.GetProperty("year").ValueKind);
        Assert.Equal(JsonValueKind.Null, created.GetProperty("hours_meter").ValueKind);
        Assert.False(created.GetProperty("includes_technical_review").GetBoolean());
        await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/products/{id}", new {
            rental_price_day = 21000, rental_price_week = (decimal?)null, rental_price_month = 710000,
            year = 2020, hours_meter = 500, platform_height_m = 13m, working_height_m = 15m,
            rental_includes_technical_advice = false, rental_includes_onsite_service = true,
            rental_includes_transport_coordination = false
        }));
        var reload = await client.GetFromJsonAsync<JsonElement>($"/api/products/{slug}");
        Assert.Equal("rental", reload.GetProperty("commercial_mode").GetString());
        Assert.Equal(21000, reload.GetProperty("rental_price_day").GetDecimal());
        Assert.Equal(JsonValueKind.Null, reload.GetProperty("rental_price_week").ValueKind);
        Assert.Equal(710000, reload.GetProperty("rental_price_month").GetDecimal());
        Assert.Equal(13m, reload.GetProperty("platform_height_m").GetDecimal());
        Assert.Equal(15m, reload.GetProperty("working_height_m").GetDecimal());
        Assert.False(reload.GetProperty("rental_includes_technical_advice").GetBoolean());
        Assert.True(reload.GetProperty("rental_includes_onsite_service").GetBoolean());
        Assert.False(reload.GetProperty("rental_includes_transport_coordination").GetBoolean());
        await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync($"/api/products/{id}", new { year = (int?)null, hours_meter = (int?)null, platform_height_m = (decimal?)null }));
        using var scope = _factory.Services.CreateScope();
        var saved = await scope.ServiceProvider.GetRequiredService<JemNexusDbContext>().Products.AsNoTracking().SingleAsync(p => p.Id == id);
        Assert.Null(saved.Year); Assert.Null(saved.HoursMeter); Assert.Null(saved.PlatformHeightM);
        Assert.Equal(15m, saved.WorkingHeightM); Assert.Equal(21000m, saved.RentalPriceDay);
    }

    [Theory]
    [InlineData("rental_price_day", "-1")]
    [InlineData("rental_price_week", "1.5")]
    [InlineData("rental_price_month", "1000000000000")]
    [InlineData("rental_price_day", "\"123\"")]
    [InlineData("rental_price_week", "\"\"")]
    [InlineData("rental_price_month", "true")]
    [InlineData("price_currency", "\"USD\"")]
    [InlineData("price_tax_mode", "\"vat_included\"")]
    [InlineData("price", "18999")]
    [InlineData("commercial_mode", "\"invalid\"")]
    [InlineData("platform_height_m", "0")]
    [InlineData("working_height_m", "1.234")]
    [InlineData("year", "0")]
    [InlineData("hours_meter", "-1")]
    public async Task RentalRejectsInvalidAmountsAndCommercialRulesOnCreateAndPatch(string key, string raw)
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var payload = RentalPayload(); payload[key] = JsonSerializer.Deserialize<JsonElement>(raw);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/products", payload)).StatusCode);
        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", RentalPayload()));
        var id = created.GetProperty("id").GetInt32();
        var response = await client.PatchAsync($"/api/products/{id}", new StringContent("{\"" + key + "\":" + raw + "}", Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task RentalPublicResponsesHideSupplierConditionStockAndHiddenTariffs()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var payload = RentalPayload(); payload["price_visible"] = false;
        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", payload));
        var id = created.GetProperty("id").GetInt32();
        foreach (var path in new[] { $"/api/public/products/{id}", "/api/public/products?commercial_mode=rental" })
        {
            var json = await client.GetFromJsonAsync<JsonElement>(path);
            var product = json.ValueKind == JsonValueKind.Array ? json.EnumerateArray().Single() : json;
            Assert.False(product.TryGetProperty("supplier", out _)); Assert.False(product.TryGetProperty("supplier_id", out _));
            Assert.DoesNotContain("proveedor@example.test", product.GetRawText());
            Assert.False(product.TryGetProperty("condition", out _)); Assert.False(product.TryGetProperty("stock_status", out _));
            Assert.Equal(JsonValueKind.Null, product.GetProperty("price").ValueKind);
            foreach (var period in new[] { "day", "week", "month" }) Assert.Equal(JsonValueKind.Null, product.GetProperty("rental_price_" + period).ValueKind);
            Assert.Equal(6200m, product.GetProperty("machine_weight_kg").GetDecimal());
            Assert.Equal(12.5m, product.GetProperty("platform_height_m").GetDecimal());
        }
        var admin = await client.GetFromJsonAsync<JsonElement>($"/api/products/{id}");
        Assert.Equal(18999m, admin.GetProperty("rental_price_day").GetDecimal());
        Assert.Equal("Proveedor", admin.GetProperty("supplier").GetProperty("name").GetString());
    }

    [Fact]
    public async Task RentalCatalogsAndFeaturedStayIsolatedFromSalesAndPromotions()
    {
        await _factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync();
        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", RentalPayload()));
        var id = created.GetProperty("id").GetInt32();
        var sales = await client.GetFromJsonAsync<JsonElement>("/api/public/products?product_type=machinery&condition=used");
        Assert.Single(sales.EnumerateArray()); Assert.Equal(1, sales[0].GetProperty("id").GetInt32());
        var all = await client.GetFromJsonAsync<JsonElement>("/api/public/products");
        Assert.DoesNotContain(all.EnumerateArray(), p => p.GetProperty("id").GetInt32() == id);
        var rental = await client.GetFromJsonAsync<JsonElement>("/api/public/products?commercial_mode=rental&product_type=machinery&condition=new&stock_status=sold&is_featured=true");
        Assert.Equal(id, Assert.Single(rental.EnumerateArray()).GetProperty("id").GetInt32());
        // Even an internally assigned rental cannot leak into existing sale-only Home slots.
        using (var scope = _factory.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<JemNexusDbContext>();
            db.HomeSectionItems.Add(new HomeSectionItem { ProductId = id, Section = HomeSections.MachineryPromotions, Position = 2, IsActive = true });
            db.Promotions.Add(new Promotion { ProductId = id, Title = "Rental should not leak", IsActive = true });
            await db.SaveChangesAsync();
        }
        var home = await client.GetFromJsonAsync<JsonElement>("/api/public/home-section-items");
        Assert.DoesNotContain(home.EnumerateArray(), item => item.GetProperty("product").GetProperty("id").GetInt32() == id);
        var promos = await client.GetFromJsonAsync<JsonElement>("/api/public/promotions");
        Assert.Empty(promos.EnumerateArray());
        var existing = await client.GetFromJsonAsync<JsonElement>("/api/products/1");
        Assert.Equal("sale", existing.GetProperty("commercial_mode").GetString());
        Assert.Equal("excavadora", existing.GetProperty("slug").GetString());
    }

    [Fact]
    public async Task RentalAllowsMissingAndExplicitZeroRatesWithoutInventingOtherRates()
    {
        await _factory.SeedCommercialDataAsync(); using var client = await CreateAuthorizedClientAsync();
        var payload = RentalPayload(); payload["rental_price_day"] = null; payload["rental_price_week"] = 0; payload.Remove("rental_price_month");
        var result = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", payload));
        Assert.Equal(JsonValueKind.Null, result.GetProperty("rental_price_day").ValueKind);
        Assert.Equal(0m, result.GetProperty("rental_price_week").GetDecimal());
        Assert.Equal(JsonValueKind.Null, result.GetProperty("rental_price_month").ValueKind);
        payload["category"] = 2; payload["product_type"] = "spare_part";
        Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/products", payload)).StatusCode);
    }

    [Fact]
    public void RentalMigrationPreservesExistingSalesAndAddsOnlyIndependentNullableData()
    {
        using var db = new JemNexusDbContext(new DbContextOptionsBuilder<JemNexusDbContext>()
            .UseSqlServer("Server=(localdb)\\MSSQLLocalDB;Database=RentalMigrationScriptOnly;Trusted_Connection=True").Options);
        var sql = db.GetService<IMigrator>().GenerateScript("20260922000000_AddCommercialQuoteIssuedBy", "20261020000000_AddMachineryRental");
        Assert.Contains("DEFAULT N'sale'", sql);
        Assert.Contains("[RentalPriceDay] decimal(12,0) NULL", sql); Assert.Contains("[PlatformHeightM] decimal(8,2) NULL", sql);
        Assert.DoesNotContain("UPDATE [Products]", sql); Assert.DoesNotContain("DROP COLUMN", sql);
        var model = db.GetService<IDesignTimeModel>().Model.FindEntityType(typeof(Product))!;
        Assert.Equal("sale", model.FindProperty("CommercialMode")!.GetDefaultValue());
        Assert.True(model.FindProperty("RentalPriceWeek")!.IsNullable);
        Assert.False(db.Database.HasPendingModelChanges());
    }
    [Fact]
    public async Task RentalQuoteStaysAssociatedAndRecognizableWithoutUsingTariffsAsTotals()
    {
        var notification = new CommercialPublicQuoteEndpointTests.CapturingQuoteNotificationService();
        using var factory = new CommercialWriteApiFactory(services => {
            services.RemoveAll<IQuoteNotificationService>();
            services.AddSingleton<IQuoteNotificationService>(notification);
        });
        await factory.SeedCommercialDataAsync();
        using var client = await CreateAuthorizedClientAsync(factory);
        var created = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", RentalPayload()));
        var id = created.GetProperty("id").GetInt32();
        using var anonymous = factory.CreateClient();
        var quote = await ReadJsonAsync<JsonElement>(await anonymous.PostAsJsonAsync("/api/public/quote-requests", new {
            product = id, customer_name = "Cliente de prueba aislado", customer_phone = "+56912345678", message = "Consultar disponibilidad"
        }));
        Assert.Equal(id, quote.GetProperty("product").GetInt32());
        Assert.StartsWith("Solicitud de arriendo.", quote.GetProperty("message").GetString());
        Assert.False(quote.TryGetProperty("total", out _)); Assert.False(quote.TryGetProperty("supplier", out _));
        Assert.Equal(id, notification.LastQuote!.ProductId);
        Assert.Equal("rental", notification.LastQuote.Product!.CommercialMode);
    }

    [Fact]
    public async Task RentalAndSaleOfSameModelHaveIndependentIdsSlugsAndPlatformHeight()
    {
        await _factory.SeedCommercialDataAsync(); using var client = await CreateAuthorizedClientAsync();
        var payload = RentalPayload(); payload["name"] = "Excavadora";
        var rental = await ReadJsonAsync<JsonElement>(await client.PostAsJsonAsync("/api/products", payload));
        Assert.NotEqual(1, rental.GetProperty("id").GetInt32());
        Assert.NotEqual("excavadora", rental.GetProperty("slug").GetString());
        await ReadJsonAsync<JsonElement>(await client.PatchAsJsonAsync("/api/products/1", new { platform_height_m = 8m, working_height_m = 10m, price = 999999m }));
        var sale = await client.GetFromJsonAsync<JsonElement>("/api/public/products/excavadora");
        Assert.Equal("sale", sale.GetProperty("commercial_mode").GetString());
        Assert.Equal(8m, sale.GetProperty("platform_height_m").GetDecimal());
        Assert.Equal(10m, sale.GetProperty("working_height_m").GetDecimal());
        Assert.Equal(999999m, sale.GetProperty("price").GetDecimal());
        var rentalReload = await client.GetFromJsonAsync<JsonElement>("/api/public/products/" + rental.GetProperty("slug").GetString());
        Assert.Equal(12.5m, rentalReload.GetProperty("platform_height_m").GetDecimal());
        Assert.Equal(18999m, rentalReload.GetProperty("rental_price_day").GetDecimal());
    }

}
