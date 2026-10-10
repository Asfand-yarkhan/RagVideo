// Calls to the FastAPI backend. In development Vite proxies /api to it.
const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error("Can't reach the server. Is the backend running?")
  }
  if (!response.ok) throw new Error(await errorMessage(response))
  return response
}

async function errorMessage(response) {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) return data.detail[0]?.msg ?? 'Invalid request.'
  } catch {
    /* not JSON */
  }
  return `Something went wrong (${response.status}).`
}

export async function processVideo(url) {
  const response = await request('/api/videos', { method: 'POST', body: JSON.stringify({ url }) })
  return response.json()
}

export async function getInsights(videoId) {
  const response = await request(`/api/videos/${videoId}/insights`)
  return response.json()
}

export async function createPost(videoId, options) {
  const response = await request(`/api/videos/${videoId}/posts`, { method: 'POST', body: JSON.stringify(options) })
  return response.json()
}

// Streams the answer, calling onToken with each new piece of text.
export async function chat(videoId, message, history, onToken) {
  const response = await request(`/api/videos/${videoId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  })
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    onToken(decoder.decode(value, { stream: true }))
  }
}
