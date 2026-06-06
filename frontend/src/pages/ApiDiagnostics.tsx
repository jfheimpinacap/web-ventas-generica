import { FormEvent, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Seo } from '../components/common/Seo'
import { API_BASE_URL, API_PROVIDER, ApiError, buildApiUrl } from '../services/api'
import { getMeWithAccessToken, loginWithoutPersistingSession } from '../services/authApi'
import { getConfiguredApiHealth, getHealthEndpoint } from '../services/healthApi'
import type { AuthUser } from '../types/catalog'
import { buildPublicUrl } from '../utils/seo'

type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

interface AuthDiagnosticResult {
  accessTokenReceived: boolean
  refreshTokenReceived: boolean
  user?: AuthUser
}

function getSafeErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return 'No fue posible conectar con la API configurada. Revisa red, URL base o CORS.'
    }

    if (error.status === 401) {
      return 'La API respondió 401 Unauthorized. Revisa credenciales o token Bearer.'
    }

    if (error.status >= 500) {
      return `La API respondió error ${error.status}. Revisa el estado del backend configurado.`
    }

    return `La API respondió error ${error.status}: ${error.message}`
  }

  if (error instanceof TypeError) {
    return 'Error de red o CORS al contactar la API configurada. Confirma URL, HTTPS y Access-Control-Allow-Origin.'
  }

  return 'Ocurrió un error inesperado al ejecutar el diagnóstico.'
}

function summarizePayload(payload: unknown) {
  if (payload === null || payload === undefined || payload === '') {
    return 'Sin payload.'
  }

  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return 'Payload recibido, pero no fue posible resumirlo como JSON.'
  }
}

function getUserRole(user?: AuthUser) {
  if (!user) return 'No informado'

  const record = user as unknown as Record<string, unknown>
  const role = record.role ?? record.roles ?? record.userRole ?? record.user_role

  if (Array.isArray(role)) {
    return role.join(', ') || 'No informado'
  }

  if (typeof role === 'string' && role.trim()) {
    return role
  }

  if (record.is_staff === true) {
    return 'staff'
  }

  return 'No informado'
}

export function ApiDiagnostics() {
  const [healthStatus, setHealthStatus] = useState<RequestStatus>('idle')
  const [healthPayload, setHealthPayload] = useState<unknown>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginStatus, setLoginStatus] = useState<RequestStatus>('idle')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [authResult, setAuthResult] = useState<AuthDiagnosticResult | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)

  const [meStatus, setMeStatus] = useState<RequestStatus>('idle')
  const [meError, setMeError] = useState<string | null>(null)
  const [meUser, setMeUser] = useState<AuthUser | null>(null)

  const healthEndpoint = getHealthEndpoint()
  const healthUrl = useMemo(() => buildApiUrl(healthEndpoint).toString(), [healthEndpoint])

  const handleHealthCheck = async () => {
    setHealthStatus('loading')
    setHealthError(null)
    setHealthPayload(null)

    try {
      const result = await getConfiguredApiHealth()
      setHealthPayload(result.payload)
      setHealthStatus('success')
    } catch (error) {
      setHealthError(getSafeErrorMessage(error))
      setHealthStatus('error')
    }
  }

  const handleLoginCheck = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoginStatus('loading')
    setLoginError(null)
    setAuthResult(null)
    setAccessToken(null)
    setMeStatus('idle')
    setMeError(null)
    setMeUser(null)

    try {
      const tokens = await loginWithoutPersistingSession(username, password)
      setAccessToken(tokens.accessToken)
      setAuthResult({
        accessTokenReceived: Boolean(tokens.accessToken),
        refreshTokenReceived: Boolean(tokens.refreshToken),
        user: tokens.user,
      })
      setLoginStatus('success')
    } catch (error) {
      setLoginError(getSafeErrorMessage(error))
      setLoginStatus('error')
    }
  }

  const handleMeCheck = async () => {
    if (!accessToken) {
      setMeError('Primero ejecuta un login válido para obtener un access token en memoria.')
      setMeStatus('error')
      return
    }

    setMeStatus('loading')
    setMeError(null)
    setMeUser(null)

    try {
      const user = await getMeWithAccessToken(accessToken)
      setMeUser(user)
      setMeStatus('success')
    } catch (error) {
      setMeError(getSafeErrorMessage(error))
      setMeStatus('error')
    }
  }

  return (
    <main className="diagnostics-page">
      <Seo
        title="Diagnóstico API | JEM Nexus"
        description="Validación controlada de la API configurada por variables Vite."
        canonical={buildPublicUrl('/diagnostico-api')}
        ogType="website"
        ogUrl={buildPublicUrl('/diagnostico-api')}
        robots="noindex,nofollow"
      />

      <section className="diagnostics-card">
        <p className="diagnostics-card__eyebrow">Validación controlada</p>
        <h1>Diagnóstico de API configurada</h1>
        <p>
          Esta pantalla permite probar health, login y <code>/auth/me</code> contra el proveedor configurado por
          variables Vite sin cambiar el comportamiento público del sitio.
        </p>

        <div className="diagnostics-grid diagnostics-grid--config">
          <div>
            <span>Proveedor API</span>
            <strong>{API_PROVIDER}</strong>
          </div>
          <div>
            <span>Base URL</span>
            <strong>{API_BASE_URL}</strong>
          </div>
          <div>
            <span>Endpoint health</span>
            <strong>{healthEndpoint}</strong>
          </div>
          <div>
            <span>URL health resuelta</span>
            <strong>{healthUrl}</strong>
          </div>
        </div>
      </section>

      <section className="diagnostics-card">
        <div className="diagnostics-card__header">
          <div>
            <p className="diagnostics-card__eyebrow">Health check</p>
            <h2>Probar health</h2>
          </div>
          <button type="button" className="btn btn--accent" onClick={handleHealthCheck} disabled={healthStatus === 'loading'}>
            {healthStatus === 'loading' ? 'Probando…' : 'Probar health'}
          </button>
        </div>

        {healthStatus === 'success' ? <p className="ui-note ui-note--success">Health OK contra la API configurada.</p> : null}
        {healthStatus === 'error' && healthError ? <p className="ui-note ui-note--error">{healthError}</p> : null}

        <pre className="diagnostics-payload" aria-label="Payload resumido del health">
          {summarizePayload(healthPayload)}
        </pre>
      </section>

      <section className="diagnostics-card">
        <p className="diagnostics-card__eyebrow">Autenticación manual</p>
        <h2>Probar login</h2>
        <p>
          La contraseña solo se mantiene en memoria del formulario. El token recibido para este diagnóstico no se muestra
          ni se guarda en <code>localStorage</code>.
        </p>

        <form className="diagnostics-form" onSubmit={handleLoginCheck}>
          <label>
            Usuario
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit" className="btn btn--accent" disabled={loginStatus === 'loading'}>
            {loginStatus === 'loading' ? 'Probando login…' : 'Probar login'}
          </button>
        </form>

        {loginStatus === 'error' && loginError ? <p className="ui-note ui-note--error">{loginError}</p> : null}
        {loginStatus === 'success' && authResult ? (
          <div className="diagnostics-result">
            <p className="ui-note ui-note--success">Login OK contra la API configurada.</p>
            <ul>
              <li>Usuario devuelto: {authResult.user?.username || username || 'No informado'}</li>
              <li>Rol devuelto: {getUserRole(authResult.user)}</li>
              <li>Access token recibido: {authResult.accessTokenReceived ? 'sí' : 'no'}</li>
              <li>Refresh token recibido: {authResult.refreshTokenReceived ? 'sí' : 'no'}</li>
            </ul>
          </div>
        ) : null}
      </section>

      <section className="diagnostics-card">
        <div className="diagnostics-card__header">
          <div>
            <p className="diagnostics-card__eyebrow">Bearer token en memoria</p>
            <h2>Probar /auth/me</h2>
          </div>
          <button type="button" className="btn btn--secondary" onClick={handleMeCheck} disabled={meStatus === 'loading' || !accessToken}>
            {meStatus === 'loading' ? 'Probando…' : 'Probar /auth/me'}
          </button>
        </div>

        {meStatus === 'error' && meError ? <p className="ui-note ui-note--error">{meError}</p> : null}
        {meStatus === 'success' && meUser ? (
          <div className="diagnostics-result">
            <p className="ui-note ui-note--success">/auth/me OK usando Bearer token normalizado.</p>
            <ul>
              <li>Usuario: {meUser.username || 'No informado'}</li>
              <li>Email: {meUser.email || 'No informado'}</li>
              <li>Rol: {getUserRole(meUser)}</li>
            </ul>
          </div>
        ) : null}
      </section>

      <section className="diagnostics-card diagnostics-card--warning">
        <h2>Notas de seguridad</h2>
        <ul>
          <li>No se muestran tokens, passwords ni headers Authorization completos.</li>
          <li>No se persiste la sesión de esta prueba en localStorage.</li>
          <li>No publiques capturas que incluyan usuarios reales o respuestas sensibles.</li>
        </ul>
        <Link to="/" className="diagnostics-card__backlink">
          ← Volver al sitio público
        </Link>
      </section>
    </main>
  )
}
