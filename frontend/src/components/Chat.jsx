import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { chat } from '../api.js'
import { linkTimestamps } from '../utils.js'

function ExternalLink(props) {
  return <a {...props} target="_blank" rel="noreferrer" />
}

export default function Chat({ videoId, suggestions }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [messages])

  async function send(text) {
    const question = text.trim()
    if (!question || busy) return
    // Keep only question/answer pairs that succeeded.
    const history = []
    for (let i = 0; i < messages.length; i += 2) {
      const [asked, answered] = [messages[i], messages[i + 1]]
      if (answered && !answered.error) history.push(asked, answered)
    }
    setMessages([...history, { role: 'user', content: question }, { role: 'assistant', content: '' }])
    setInput('')
    setBusy(true)

    const updateLast = (change) =>
      setMessages((current) => [...current.slice(0, -1), { ...current.at(-1), ...change(current.at(-1)) }])

    try {
      await chat(videoId, question, history, (token) => updateLast((last) => ({ content: last.content + token })))
      updateLast((last) => (last.content ? {} : { content: 'No answer came back. Please try again.', error: true }))
    } catch (err) {
      updateLast(() => ({ content: err.message, error: true }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p className="muted">Ask anything about the video. Answers cite timestamps you can click.</p>
            <div className="suggestions">
              {(suggestions.length ? suggestions : ['What are the main points?', 'What examples are given?']).map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, index) => (
          <div key={index} className={`msg ${m.role}${m.error ? ' error' : ''}`}>
            {m.role === 'assistant' ? (
              m.content ? (
                <Markdown components={{ a: ExternalLink }}>{linkTimestamps(m.content, videoId)}</Markdown>
              ) : (
                <span className="typing" aria-label="Thinking"><i /><i /><i /></span>
              )
            ) : (
              m.content
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the video..."
          aria-label="Your question"
          maxLength={2000}
        />
        <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  )
}
