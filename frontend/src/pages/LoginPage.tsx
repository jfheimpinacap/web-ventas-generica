import { FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError } from '../services/api'
import { NOINDEX_ROBOTS, Seo } from '../components/common/Seo'
import { canAccessSellerPanel, getMe, login, logout } from '../services/authApi'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const logoutReason = (location.state as { reason?: string } | null)?.reason ?? searchParams.get('reason')
  const idleMessage = logoutReason === 'idle' ? 'Sesión cerrada por inactividad. Vuelve a iniciar sesión para continuar.' : null

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await login(username, password)
      const currentUser = await getMe()

      if (!canAccessSellerPanel(currentUser)) {
        logout()
        setError('Tu cuenta no tiene permisos para acceder al panel vendedor.')
        return
      }

      navigate('/admin/productos', { replace: true, state: null })
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        setError('Credenciales inválidas. Verifica usuario y contraseña.')
      } else {
        setError('No fue posible iniciar sesión. Intenta nuevamente.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main id="main-content" className="login-page" tabIndex={-1}>
      <Seo
        title="Panel de administración | JEM Nexus"
        description="Acceso al panel interno de gestión comercial y soporte."
        ogType="website"
        robots={NOINDEX_ROBOTS}
      />
      <section className="login-card">
        <h1>Panel de administración</h1>
        <p>Ingresa con tu cuenta para administrar catálogo, cotizaciones y promociones.</p>

        {idleMessage ? <p className="ui-note ui-note--success" role="status">{idleMessage}</p> : null}

        <form onSubmit={handleSubmit} className="login-form" aria-busy={loading}>
          <label>
            Usuario
            <input type="text" autoComplete="username" aria-describedby={error ? 'login-error' : undefined} value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Contraseña
            <span className="login-password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                aria-describedby={error ? 'login-error' : undefined}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button type="button" className="login-password-toggle" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
                <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.75"/></svg>
              </button>
            </span>
          </label>

          {error ? <p id="login-error" className="ui-note ui-note--error" role="alert">{error}</p> : null}

          <button type="submit" className="btn btn--accent" disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>

        <Link to="/" className="login-card__backlink">
          ← Volver al sitio público
        </Link>
      </section>
    </main>
  )
}
