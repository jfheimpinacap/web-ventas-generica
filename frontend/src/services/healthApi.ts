import { API_BASE_URL, API_PROVIDER, apiRequest } from './api'

export interface ApiHealthStatus {
  baseUrl: string
  provider: typeof API_PROVIDER
  endpoint: string
  ok: boolean
  payload: unknown
}

export function getHealthEndpoint() {
  return API_PROVIDER === 'dotnet' ? '/health' : '/health/'
}

export async function getConfiguredApiHealth(): Promise<ApiHealthStatus> {
  const endpoint = getHealthEndpoint()
  const payload = await apiRequest<unknown>(endpoint)

  return {
    baseUrl: API_BASE_URL,
    provider: API_PROVIDER,
    endpoint,
    ok: true,
    payload,
  }
}
