import { FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError } from '../services/api'
import { Seo } from '../components/common/Seo'
import { canAccessSellerPanel, getMe, login, logout } from '../services/authApi'
import { buildPublicUrl } from '../utils/seo'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
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
    <main className="login-page">
      <Seo
        title="Acceso vendedor | JEM Nexus"
        description="Acceso al panel interno de gestión comercial y soporte."
        canonical={buildPublicUrl('/login')}
        ogType="website"
        ogUrl={buildPublicUrl('/login')}
        robots="noindex,nofollow"
      />
      <section className="login-card">
        <p className="login-card__eyebrow">Acceso vendedor</p>
        <h1>Panel privado</h1>
        <p>Ingresa con tu cuenta para administrar catálogo, cotizaciones y promociones.</p>

        {idleMessage ? <p className="ui-note ui-note--success">{idleMessage}</p> : null}

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Usuario
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error ? <p className="ui-note ui-note--error">{error}</p> : null}

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
