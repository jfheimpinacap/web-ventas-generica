import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../services/api'
import { getMe, login } from '../services/authApi'

export function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await login(username, password)
      await getMe()
      navigate('/admin/productos', { replace: true })
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
      <section className="login-card">
        <p className="login-card__eyebrow">Acceso vendedor</p>
        <h1>Panel privado</h1>
        <p>Ingresa con tu cuenta para administrar catálogo, cotizaciones y promociones.</p>

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
