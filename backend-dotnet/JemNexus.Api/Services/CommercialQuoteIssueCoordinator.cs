using System.Collections.Concurrent;

namespace JemNexus.Api.Services;

public sealed class CommercialQuoteIssueCoordinator
{
    private readonly ConcurrentDictionary<(int SellerId, Guid Key), Entry> _entries = new();

    public async ValueTask<IAsyncDisposable> AcquireAsync(int sellerId, Guid key, CancellationToken cancellationToken)
    {
        var mapKey = (sellerId, key);
        Entry entry;
        while (true)
        {
            entry = _entries.GetOrAdd(mapKey, static _ => new Entry());
            lock (entry)
            {
                if (!entry.Removed) { entry.References++; break; }
            }
        }
        try { await entry.Semaphore.WaitAsync(cancellationToken); }
        catch { ReleaseReference(mapKey, entry); throw; }
        return new Releaser(this, mapKey, entry);
    }

    private void Release((int SellerId, Guid Key) key, Entry entry)
    {
        entry.Semaphore.Release();
        ReleaseReference(key, entry);
    }

    private void ReleaseReference((int SellerId, Guid Key) key, Entry entry)
    {
        lock (entry)
        {
            entry.References--;
            if (entry.References != 0) return;
            entry.Removed = true;
            _entries.TryRemove(key, out _);
        }
        entry.Semaphore.Dispose();
    }

    private sealed class Entry { public readonly SemaphoreSlim Semaphore = new(1, 1); public int References; public bool Removed; }
    private sealed class Releaser(CommercialQuoteIssueCoordinator owner, (int, Guid) key, Entry entry) : IAsyncDisposable
    {
        private int _released;
        public ValueTask DisposeAsync() { if (Interlocked.Exchange(ref _released, 1) == 0) owner.Release(key, entry); return ValueTask.CompletedTask; }
    }
}
