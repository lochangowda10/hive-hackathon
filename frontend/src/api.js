// Single place every backend call goes through.
// Uses relative /api paths — the Vite dev proxy forwards them to FastAPI.

const TOKEN_KEY = 'swinglens_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

async function request(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  let data = null
  try { data = await res.json() } catch { /* non-JSON error body */ }

  if (!res.ok) {
    const detail = data?.detail
    const message =
      typeof detail === 'string' ? detail
      : detail?.message ? `${detail.message}${detail.hint ? ` ${detail.hint}` : ''}`
      : `Request failed (${res.status})`
    const err = new Error(message)
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  register: (username, email, password) =>
    request('/api/auth/register', { method: 'POST', body: { username, email, password } }),
  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request('/api/auth/me'),

  searchStocks: (q) => request(`/api/stocks/search?q=${encodeURIComponent(q)}`),
  candles: (symbol, range, interval) =>
    request(`/api/stocks/${encodeURIComponent(symbol)}/candles?range=${range}&interval=${interval}`),

  aiChat: (message, context, conversation_id) =>
    request('/api/ai/chat', { method: 'POST', body: { message, context, conversation_id } }),
  aiConversations: () => request('/api/ai/conversations'),
  aiMessages: (id) => request(`/api/ai/conversations/${id}/messages`),
  aiDeleteConversation: (id) => request(`/api/ai/conversations/${id}`, { method: 'DELETE' }),
  runScan: (segment, top = 5) => request(`/api/scan?segment=${encodeURIComponent(segment)}&top=${top}`),

  importPortfolio: async (file, broker) => {
    const form = new FormData()
    form.append('file', file)
    form.append('broker', broker)
    const headers = {}
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch('/api/portfolio/import', { method: 'POST', headers, body: form })
    let data = null
    try { data = await res.json() } catch { /* non-JSON */ }
    if (!res.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Import failed (${res.status})`)
    return data
  },
  watchlist: () => request('/api/watchlist'),
  toggleWatch: (symbol, name) =>
    request(`/api/watchlist/${encodeURIComponent(symbol)}?name=${encodeURIComponent(name || '')}`, { method: 'POST' }),
  alerts: () => request('/api/alerts'),
  createAlert: (symbol, price, direction) =>
    request(`/api/alerts?symbol=${encodeURIComponent(symbol)}&price=${price}&direction=${direction}`, { method: 'POST' }),
  deleteAlert: (id) => request(`/api/alerts/${id}`, { method: 'DELETE' }),
  checkAlerts: () => request('/api/alerts/check', { method: 'POST' }),
  trackRecord: () => request('/api/track-record', { method: 'POST' }),

  portfolioSummary: () => request('/api/portfolio/summary'),
  portfolioBehavior: () => request('/api/portfolio/behavior'),
  clearPortfolio: () => request('/api/portfolio', { method: 'DELETE' }),
  aiStatus: () => request('/api/ai/status'),

  analyze: (symbol, range, interval) =>
    request(`/api/analysis/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`, { method: 'POST' }),
  myPlans: () => request('/api/analysis/plans'),

  newsMarket: () => request('/api/news/market'),
  newsSymbol: (symbol) => request(`/api/news/${encodeURIComponent(symbol)}`),

  marketSegments: () => request('/api/markets/segments'),
  marketsOverview: () => request('/api/markets/overview'),
  marketSegment: (id) => request(`/api/markets/${encodeURIComponent(id)}`),

  indicatorCatalog: () => request('/api/indicators'),
  computeIndicators: (symbol, range, interval, indicators) =>
    request(`/api/indicators/${encodeURIComponent(symbol)}`, {
      method: 'POST',
      body: { range, interval, indicators },
    }),

  research: (symbol) => request(`/api/research/${encodeURIComponent(symbol)}`),
  researchFinancials: (symbol) => request(`/api/research/${encodeURIComponent(symbol)}/financials`),
  discoveryLists: () => request('/api/research/discovery/lists'),
  discovery: (listId, universe = 'india_large') =>
    request(`/api/research/discovery/${encodeURIComponent(listId)}?universe=${encodeURIComponent(universe)}`),
}
