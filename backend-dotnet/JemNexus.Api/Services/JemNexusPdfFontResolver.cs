using PdfSharp.Fonts;

namespace JemNexus.Api.Services;

public static class JemNexusPdfFontResolver
{
    private static readonly object Sync = new();
    private static bool _configured;

    public static void EnsureConfigured()
    {
        lock (Sync)
        {
            if (_configured) return;
            if (!OperatingSystem.IsWindows())
                throw new PlatformNotSupportedException("La generación PDF requiere las fuentes Arial del despliegue IIS/Windows.");
            GlobalFontSettings.UseWindowsFontsUnderWindows = true;
            _configured = true;
        }
    }
}
