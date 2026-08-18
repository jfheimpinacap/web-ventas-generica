namespace JemNexus.Api.Services;

public static class ChileTime
{
    public static TimeZoneInfo Zone { get; } = ResolveZone();

    public static (DateTime Utc, DateOnly LocalDate) Current(TimeProvider timeProvider)
    {
        var utc = timeProvider.GetUtcNow();
        var local = TimeZoneInfo.ConvertTime(utc, Zone);
        return (utc.UtcDateTime, DateOnly.FromDateTime(local.DateTime));
    }

    private static TimeZoneInfo ResolveZone()
    {
        try { return TimeZoneInfo.FindSystemTimeZoneById("America/Santiago"); }
        catch (TimeZoneNotFoundException) { return TimeZoneInfo.FindSystemTimeZoneById("Pacific SA Standard Time"); }
    }
}
