import assert from 'node:assert/strict'
import test from 'node:test'

import { composeApiUrl } from '../src/services/apiUrl.ts'

const origins = ['http://localhost:5000', 'http://localhost:5000/api']

test('composes short and canonical protected paths with one api prefix', () => {
  for (const base of origins) {
    for (const path of ['/technical-sheets/7/file', '/api/technical-sheets/7/file']) {
      assert.equal(composeApiUrl(base, path).href, 'http://localhost:5000/api/technical-sheets/7/file')
    }
  }
})

test('keeps health at the origin for every supported base', () => {
  for (const base of origins) {
    assert.equal(composeApiUrl(base, '/health').href, 'http://localhost:5000/health')
  }
})

test('preserves the canonical public technical-sheet path', () => {
  for (const base of origins) {
    assert.equal(
      composeApiUrl(base, '/api/public/products/modelo/technical-sheet/file').href,
      'http://localhost:5000/api/public/products/modelo/technical-sheet/file',
    )
  }
})

test('preserves query values and sets download exactly once', () => {
  const url = composeApiUrl(
    'http://localhost:5000/api/',
    '/api/technical-sheets/7/file?locale=es&download=false',
    { download: true },
  )
  assert.equal(url.href, 'http://localhost:5000/api/technical-sheets/7/file?locale=es&download=true')
  assert.deepEqual(url.searchParams.getAll('download'), ['true'])
})

test('normalizes leading and repeated path slashes with trailing base slashes', () => {
  assert.equal(
    composeApiUrl('http://localhost:5000///', 'technical-sheets//7/file').href,
    'http://localhost:5000/api/technical-sheets/7/file',
  )
  assert.equal(
    composeApiUrl('http://localhost:5000/api/', '/api//technical-sheets/7/file').href,
    'http://localhost:5000/api/technical-sheets/7/file',
  )
})

test('rejects absolute and protocol-relative destinations before fetch', () => {
  for (const path of ['http://evil.example/file', 'https://evil.example/file', '//evil.example/file']) {
    assert.throws(() => composeApiUrl(origins[0], path), TypeError)
  }
})
