import { useState } from 'react'

export default function UrlForm({ onSubmit, loading }) {
  const [url, setUrl] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    if (url.trim() && !loading) onSubmit(url.trim())
  }

  return (
    <form className="url-form" onSubmit={handleSubmit}>
      <input
        type="text"
        inputMode="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://www.youtube.com/watch?v=..."
        aria-label="YouTube video link"
        disabled={loading}
      />
      <button type="submit" className="btn btn-primary" disabled={loading || !url.trim()}>
        {loading ? <span className="spinner" aria-label="Loading" /> : 'Process video'}
      </button>
    </form>
  )
}
