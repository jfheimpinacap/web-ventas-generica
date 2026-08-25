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
    internal const string UsdDisclosure = "Valores expresados en dólares estadounidenses (USD). En caso de aceptar la cotización se aplicará el valor del dólar observado a la fecha de emisión de la factura.";
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
        AddFooter(section, quote);
        AddHeader(section, quote);
        AddInformation(section, quote);
        AddItems(section, quote);
        AddTotals(section, quote);
        if (!string.IsNullOrWhiteSpace(quote.DetailedDescription))
        {
            AddHeading(section, "ESPECIFICACIONES TÉCNICAS");
            AddMultilineText(section, quote.DetailedDescription);
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
        AddRight(row.Cells[1], $"Fecha: {quote.IssuedOn:dd-MM-yyyy}");
        var line = section.AddParagraph(); line.Format.Borders.Bottom.Width = 2; line.Format.Borders.Bottom.Color = Color.Parse("#0077B6"); line.Format.SpaceAfter = 7;
    }

    private static void AddInformation(Section section, CommercialQuote quote)
    {
        AddHeading(section, "DATOS DEL CLIENTE");
        AddInformationGrid(section,
            ("Razón social", quote.CustomerBusinessName, "RUT", quote.CustomerRut),
            ("Actividad o giro", quote.CustomerBusinessActivity, "Dirección", quote.CustomerAddress),
            ("Comuna o ciudad", quote.CustomerCityOrCommune, "Nombre de contacto", quote.CustomerContactName),
            ("Teléfono", quote.CustomerPhone, "Correo electrónico", quote.CustomerEmail));

        AddHeading(section, "DATOS COMERCIALES");
        AddInformationGrid(section,
            ("Vendedor", quote.ResponsibleSellerName, "Correo", quote.ResponsibleSellerEmail),
            ("Teléfono", quote.ResponsibleSellerPhone, "Código de vendedor", quote.ResponsibleSellerCode),
            ("Condición de venta", quote.SaleCondition == CommercialQuoteSaleConditions.Cash ? "Contado" : "Crédito a 30 días", "Vigencia", $"{quote.ValidityDays} días"),
            ("Fecha de emisión", $"{quote.IssuedOn:dd-MM-yyyy}", "Folio", quote.Folio));
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
            AddNumber(row.Cells[4], Money(item.UnitNetAmount, quote.Currency));
            AddNumber(row.Cells[5], item.DiscountPercent.ToString("N0", ChileanCulture) + " %"); AddNumber(row.Cells[6], Money(item.LineNetAmount, quote.Currency));
        }
    }

    private static void AddTotals(Section section, CommercialQuote quote)
    {
        var table = section.AddTable();
        table.AddColumn(Unit.FromInch(5.25));
        table.AddColumn(Unit.FromInch(.75));
        table.AddColumn(Unit.FromInch(1.4));
        var netRow = table.AddRow();
        netRow.Cells[0].MergeDown = 2;
        if (quote.Currency == CommercialQuoteCurrencies.Usd)
        {
            var disclosure = netRow.Cells[0].AddParagraph(UsdDisclosure);
            disclosure.Format.RightIndent = Unit.FromInch(.25);
        }
        AddTotal(netRow, "Neto", Money(quote.NetAmount, quote.Currency), false);
        AddTotal(table.AddRow(), $"IVA ({quote.TaxRatePercent.ToString("N2", ChileanCulture)} %)", Money(quote.TaxAmount, quote.Currency), false);
        AddTotal(table.AddRow(), "TOTAL", Money(quote.TotalAmount, quote.Currency), true);
        table.Format.SpaceBefore = 7;
        table.Format.SpaceAfter = 8;
    }

    private static void AddFooter(Section section, CommercialQuote quote)
    {
        var footer = section.Footers.Primary.AddParagraph(); footer.Format.Font.Size = 8; footer.Format.Font.Color = Color.Parse("#6B7280");
        var sellerContact = new[] { quote.ResponsibleSellerName, quote.ResponsibleSellerPhone }
            .Where(value => !string.IsNullOrWhiteSpace(value)).Select(Normalize);
        var segments = new[] { "JEM Nexus", "https://jem-nexus.cl", quote.Folio, string.Join(" · ", sellerContact) }
            .Where(value => !string.IsNullOrWhiteSpace(value));
        footer.AddText(string.Join(" · ", segments) + " · Página ");
        footer.AddPageField(); footer.AddText(" de "); footer.AddNumPagesField();
    }

    private static void AddInformationGrid(Section section, params (string LeftLabel, string? LeftValue, string RightLabel, string? RightValue)[] fields)
    {
        var table = section.AddTable();
        var leftColumn = table.AddColumn(Unit.FromInch(3.7));
        var rightColumn = table.AddColumn(Unit.FromInch(3.7));
        leftColumn.LeftPadding = rightColumn.LeftPadding = 5;
        leftColumn.RightPadding = rightColumn.RightPadding = 5;
        table.Borders.Color = Color.Parse("#9CA3AF"); table.Borders.Width = .6;
        foreach (var field in fields)
        {
            var row = table.AddRow(); row.TopPadding = 4; row.BottomPadding = 4;
            AddField(row.Cells[0], field.LeftLabel, field.LeftValue);
            AddField(row.Cells[1], field.RightLabel, field.RightValue);
        }
        table.Format.SpaceAfter = 6;
    }

    private static void AddMultilineText(Section section, string value)
    {
        var paragraph = section.AddParagraph();
        var lines = Normalize(value).Split('\n');
        for (var index = 0; index < lines.Length; index++)
        {
            if (index > 0) paragraph.AddLineBreak();
            paragraph.AddText(lines[index]);
        }
        paragraph.Format.SpaceAfter = 8;
    }

    private static void AddHeading(Section section, string value) { var p = section.AddParagraph(value); StyleHeading(p); }
    private static void AddHeading(Cell cell, string value) { var p = cell.AddParagraph(value); StyleHeading(p); }
    private static void StyleHeading(Paragraph p) { p.Format.Font.Bold = true; p.Format.Font.Color = Color.Parse("#042149"); p.Format.SpaceBefore = 3; p.Format.SpaceAfter = 4; }
    private static void AddField(Cell cell, string label, string? value) { var p = cell.AddParagraph(); p.AddFormattedText(label + ": ", TextFormat.Bold); p.AddText(string.IsNullOrWhiteSpace(value) ? "No informado" : Normalize(value)); }
    private static void AddRight(Cell cell, string value) { var p = cell.AddParagraph(value); p.Format.Alignment = ParagraphAlignment.Right; }
    private static void AddNumber(Cell cell, string value) { var p = cell.AddParagraph(value); p.Format.Alignment = ParagraphAlignment.Right; }
    private static void AddTotal(Row row, string label, string value, bool strong) { AddNumber(row.Cells[1], label); AddNumber(row.Cells[2], value); row.Format.Font.Bold = strong; if (strong) { row.Cells[1].Shading.Color = Color.Parse("#EAF4F8"); row.Cells[2].Shading.Color = Color.Parse("#EAF4F8"); row.Format.Font.Size = 10; row.Format.Font.Color = Color.Parse("#042149"); } }
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
