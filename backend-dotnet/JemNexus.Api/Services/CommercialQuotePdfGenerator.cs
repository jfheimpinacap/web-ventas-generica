using System.Globalization;
using System.Text;
using JemNexus.Api.Models;
using MigraDoc.DocumentObjectModel;
using MigraDoc.DocumentObjectModel.Tables;
using MigraDoc.Rendering;

namespace JemNexus.Api.Services;

public sealed class CommercialQuotePdfGenerator : ICommercialQuotePdfGenerator
{
    internal const string LogoResourceName = "JemNexus.Api.Assets.jem-nexus.png";
    private const string FontName = "Arial";
    private static readonly CultureInfo ChileanCulture = CultureInfo.GetCultureInfo("es-CL");
    private readonly string _logoData;

    public CommercialQuotePdfGenerator()
    {
        using var stream = typeof(CommercialQuotePdfGenerator).Assembly.GetManifestResourceStream(LogoResourceName)
            ?? throw new InvalidOperationException($"No se encontró el recurso embebido {LogoResourceName}.");
        using var memory = new MemoryStream();
        stream.CopyTo(memory);
        _logoData = "base64:" + Convert.ToBase64String(memory.ToArray());
    }

    public byte[] Generate(CommercialQuote quote)
    {
        ArgumentNullException.ThrowIfNull(quote);
        if (quote.Status != CommercialQuoteStatuses.Issued || string.IsNullOrWhiteSpace(quote.Folio) || quote.IssuedOn is null)
            throw new ArgumentException("Solo se pueden generar cotizaciones emitidas con folio.", nameof(quote));

        var document = CreateDocument(quote);
        var renderer = new PdfDocumentRenderer() { Document = document };
        renderer.RenderDocument();
        renderer.PdfDocument.Info.Title = $"Cotización {quote.Folio}";
        renderer.PdfDocument.Info.Author = "JEM Nexus";
        renderer.PdfDocument.Info.Subject = "Cotización comercial";
        renderer.PdfDocument.Info.Creator = "JEM Nexus API";
        using var output = new MemoryStream();
        renderer.PdfDocument.Save(output, closeStream: false);
        return output.ToArray();
    }

    private Document CreateDocument(CommercialQuote quote)
    {
        var document = new Document();
        document.Info.Title = $"Cotización {quote.Folio}";
        document.Info.Author = "JEM Nexus";
        document.Info.Subject = "Cotización comercial";
        var normal = document.Styles[StyleNames.Normal]!;
        normal.Font.Name = FontName;
        normal.Font.Size = 8.5;
        normal.Font.Color = Color.Parse("#1F2937");

        var section = document.AddSection();
        section.PageSetup.PageFormat = PageFormat.Letter;
        section.PageSetup.Orientation = Orientation.Portrait;
        section.PageSetup.LeftMargin = Unit.FromInch(.5);
        section.PageSetup.RightMargin = Unit.FromInch(.5);
        section.PageSetup.TopMargin = Unit.FromInch(.5);
        section.PageSetup.BottomMargin = Unit.FromInch(.58);
        AddFooter(section, quote.Folio!);
        AddHeader(section, quote);
        AddInformation(section, quote);
        AddItems(section, quote);
        AddTotals(section, quote);
        if (!string.IsNullOrWhiteSpace(quote.DetailedDescription))
        {
            AddHeading(section, "OBSERVACIONES");
            var observations = section.AddParagraph(Normalize(quote.DetailedDescription));
            observations.Format.SpaceAfter = 8;
        }
        return document;
    }

    private void AddHeader(Section section, CommercialQuote quote)
    {
        var table = section.AddTable();
        table.AddColumn(Unit.FromInch(3.9)); table.AddColumn(Unit.FromInch(3.5));
        var row = table.AddRow();
        var image = row.Cells[0].AddImage(_logoData); image.LockAspectRatio = true; image.Width = Unit.FromInch(2.25);
        var title = row.Cells[1].AddParagraph("COTIZACIÓN"); title.Format.Alignment = ParagraphAlignment.Right;
        title.Format.Font.Size = 20; title.Format.Font.Bold = true; title.Format.Font.Color = Color.Parse("#042149");
        AddRight(row.Cells[1], $"Folio: {quote.Folio}");
        AddRight(row.Cells[1], $"Estado: Emitida");
        AddRight(row.Cells[1], $"Fecha: {quote.IssuedOn:dd-MM-yyyy} · Moneda: {quote.Currency}");
        var line = section.AddParagraph(); line.Format.Borders.Bottom.Width = 2; line.Format.Borders.Bottom.Color = Color.Parse("#0077B6"); line.Format.SpaceAfter = 7;
    }

    private static void AddInformation(Section section, CommercialQuote quote)
    {
        var table = section.AddTable(); table.AddColumn(Unit.FromInch(3.65)); table.AddColumn(Unit.FromInch(3.75));
        var row = table.AddRow();
        AddHeading(row.Cells[0], "DATOS DEL CLIENTE");
        AddField(row.Cells[0], "Razón social", quote.CustomerBusinessName); AddField(row.Cells[0], "RUT", quote.CustomerRut);
        AddField(row.Cells[0], "Actividad o giro", quote.CustomerBusinessActivity); AddField(row.Cells[0], "Dirección", quote.CustomerAddress);
        AddField(row.Cells[0], "Ciudad o comuna", quote.CustomerCityOrCommune); AddField(row.Cells[0], "Contacto", quote.CustomerContactName);
        AddField(row.Cells[0], "Teléfono", quote.CustomerPhone); AddField(row.Cells[0], "Correo", quote.CustomerEmail);
        AddHeading(row.Cells[1], "DATOS COMERCIALES");
        AddField(row.Cells[1], "Vendedor responsable", quote.ResponsibleSellerName); AddField(row.Cells[1], "Código vendedor", quote.ResponsibleSellerCode);
        AddField(row.Cells[1], "Condición de venta", quote.SaleCondition == CommercialQuoteSaleConditions.Cash ? "Contado" : "Crédito a 30 días");
        AddField(row.Cells[1], "Moneda", quote.Currency == CommercialQuoteCurrencies.Clp ? "Peso chileno (CLP)" : "Dólar estadounidense (USD)");
        AddField(row.Cells[1], "Vigencia", $"{quote.ValidityDays} días"); AddField(row.Cells[1], "Fecha de emisión", $"{quote.IssuedOn:dd-MM-yyyy}"); AddField(row.Cells[1], "Folio", quote.Folio);
        table.Format.SpaceAfter = 8;
    }

    private static void AddItems(Section section, CommercialQuote quote)
    {
        AddHeading(section, "PRODUCTOS O SERVICIOS");
        var table = section.AddTable(); table.Borders.Color = Color.Parse("#D1D5DB"); table.Borders.Width = .4;
        foreach (var width in new[] { .3, 2.05, 1.05, .55, 1.2, .7, 1.55 }) table.AddColumn(Unit.FromInch(width));
        var header = table.AddRow(); header.HeadingFormat = true; header.Shading.Color = Color.Parse("#EAF4F8"); header.Format.Font.Bold = true;
        string[] labels = ["#", "Producto / descripción", "Marca / modelo", "Cant.", "Neto unitario", "Dto.", "Total neto"];
        for (var index = 0; index < labels.Length; index++) header.Cells[index].AddParagraph(labels[index]);
        foreach (var item in quote.Items.OrderBy(item => item.Position))
        {
            var row = table.AddRow(); row.TopPadding = 3; row.BottomPadding = 3;
            row.Cells[0].AddParagraph(item.Position.ToString(ChileanCulture)); row.Cells[1].AddParagraph(Normalize(item.ProductName));
            row.Cells[2].AddParagraph(string.Join(" / ", new[] { item.BrandName, item.ModelName }.Where(value => !string.IsNullOrWhiteSpace(value)).Select(Normalize)));
            AddNumber(row.Cells[3], item.Quantity.ToString("N0", ChileanCulture));
            AddNumber(row.Cells[4], item.DiscountPercent == 0
                ? Money(item.UnitNetAmount, quote.Currency)
                : $"{Money(item.UnitNetAmount, quote.Currency)}\nFinal: {Money(item.FinalUnitNetAmount, quote.Currency)}");
            AddNumber(row.Cells[5], item.DiscountPercent.ToString("N2", ChileanCulture) + " %"); AddNumber(row.Cells[6], Money(item.LineNetAmount, quote.Currency));
        }
    }

    private static void AddTotals(Section section, CommercialQuote quote)
    {
        var table = section.AddTable(); table.AddColumn(Unit.FromInch(5.25)); table.AddColumn(Unit.FromInch(2.15));
        AddTotal(table, "Neto", Money(quote.NetAmount, quote.Currency), false);
        AddTotal(table, $"IVA ({quote.TaxRatePercent.ToString("N2", ChileanCulture)} %)", Money(quote.TaxAmount, quote.Currency), false);
        AddTotal(table, "TOTAL", Money(quote.TotalAmount, quote.Currency), true); table.Format.SpaceBefore = 7; table.Format.SpaceAfter = 8;
    }

    private static void AddFooter(Section section, string folio)
    {
        var footer = section.Footers.Primary.AddParagraph(); footer.Format.Font.Size = 8; footer.Format.Font.Color = Color.Parse("#6B7280");
        footer.AddText($"JEM Nexus · https://jem-nexus.cl · {folio} · Documento de cotización comercial. · Página ");
        footer.AddPageField(); footer.AddText(" de "); footer.AddNumPagesField();
    }

    private static void AddHeading(Section section, string value) { var p = section.AddParagraph(value); StyleHeading(p); }
    private static void AddHeading(Cell cell, string value) { var p = cell.AddParagraph(value); StyleHeading(p); }
    private static void StyleHeading(Paragraph p) { p.Format.Font.Bold = true; p.Format.Font.Color = Color.Parse("#042149"); p.Format.SpaceBefore = 3; p.Format.SpaceAfter = 4; }
    private static void AddField(Cell cell, string label, string? value) { if (string.IsNullOrWhiteSpace(value)) return; var p = cell.AddParagraph(); p.AddFormattedText(label + ": ", TextFormat.Bold); p.AddText(Normalize(value)); }
    private static void AddRight(Cell cell, string value) { var p = cell.AddParagraph(value); p.Format.Alignment = ParagraphAlignment.Right; }
    private static void AddNumber(Cell cell, string value) { var p = cell.AddParagraph(value); p.Format.Alignment = ParagraphAlignment.Right; }
    private static void AddTotal(Table table, string label, string value, bool strong) { var row = table.AddRow(); AddNumber(row.Cells[0], label); AddNumber(row.Cells[1], value); row.Format.Font.Bold = strong; if (strong) { row.Shading.Color = Color.Parse("#EAF4F8"); row.Format.Font.Size = 10; row.Format.Font.Color = Color.Parse("#042149"); } }
    private static string Money(decimal value, string currency) => currency == CommercialQuoteCurrencies.Clp ? $"CLP $ {value.ToString("N0", ChileanCulture)}" : $"USD US$ {value.ToString("N2", ChileanCulture)}";
    private static string Normalize(string? value)
    {
        if (string.IsNullOrEmpty(value)) return string.Empty;
        var builder = new StringBuilder(value.Length);
        foreach (var character in value.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n'))
            if (character is '\n' or '\t' || !char.IsControl(character)) builder.Append(character);
        return builder.ToString();
    }
}
