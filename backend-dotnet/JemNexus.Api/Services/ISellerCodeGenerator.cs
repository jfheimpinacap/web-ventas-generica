namespace JemNexus.Api.Services;

public interface ISellerCodeGenerator
{
    Task<string> GenerateAsync(CancellationToken cancellationToken = default);
}
