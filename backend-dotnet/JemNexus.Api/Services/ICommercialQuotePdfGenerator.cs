using JemNexus.Api.Models;

namespace JemNexus.Api.Services;

public interface ICommercialQuotePdfGenerator
{
    byte[] Generate(CommercialQuote quote);
}
