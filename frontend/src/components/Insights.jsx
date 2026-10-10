export default function Insights({ state, onRetry }) {
  if (state.status === 'loading') {
    return (
      <div className="card">
        <h2 className="card-title">Key takeaways</h2>
        <p className="muted small">Reading the whole video...</p>
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton short" />
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="card">
        <h2 className="card-title">Key takeaways</h2>
        <p className="alert">{state.error}</p>
        <button className="btn btn-ghost" onClick={onRetry}>Try again</button>
      </div>
    )
  }

  if (state.status !== 'ready') return null
  const { summary, key_points: keyPoints, quotes } = state.data

  return (
    <div className="card">
      <h2 className="card-title">Summary</h2>
      <p className="summary">{summary}</p>
      {keyPoints.length > 0 && (
        <>
          <h2 className="card-title">Key takeaways</h2>
          <ul className="points">
            {keyPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </>
      )}
      {quotes.length > 0 && (
        <>
          <h2 className="card-title">Quotable</h2>
          {quotes.map((quote) => (
            <blockquote key={quote}>{quote}</blockquote>
          ))}
        </>
      )}
    </div>
  )
}
