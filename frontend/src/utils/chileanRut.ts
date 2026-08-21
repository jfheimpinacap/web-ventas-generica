const ALLOWED_INPUT = /^[0-9kK.\s-]*$/

const compactRut = (value: string): string | null => {
  if (!ALLOWED_INPUT.test(value)) return null
  const compact = value.replace(/[.\s]/g, '').toUpperCase()
  if ((compact.match(/-/g) ?? []).length > 1) return null
  return compact.replace('-', '')
}

export function normalizeChileanRut(value: string): string | null {
  const compact = compactRut(value)
  if (!compact || compact.length < 2) return null
  const body = compact.slice(0, -1)
  const suppliedDigit = compact[compact.length - 1]
  if (!/^\d+$/.test(body) || !/^[0-9K]$/.test(suppliedDigit) || /^0+$/.test(body)) return null

  let sum = 0
  let multiplier = 2
  for (let index = body.length - 1; index >= 0; index -= 1) {
    sum += Number(body[index]) * multiplier
    multiplier = multiplier === 7 ? 2 : multiplier + 1
  }
  const remainder = 11 - (sum % 11)
  const expectedDigit = remainder === 11 ? '0' : remainder === 10 ? 'K' : String(remainder)
  return suppliedDigit === expectedDigit ? `${body}-${suppliedDigit}` : null
}

export function isValidChileanRut(value: string): boolean {
  return normalizeChileanRut(value) !== null
}

export function formatChileanRutInput(value: string): string {
  const compact = compactRut(value)
  if (compact === null) return value
  const limited = compact.slice(0, 9)
  if (limited.length < 2) return limited
  const body = limited.slice(0, -1)
  const digit = limited[limited.length - 1]
  return `${body.replace(/\B(?=(\d{3})+(?!\d))/g, '.')}-${digit}`
}
