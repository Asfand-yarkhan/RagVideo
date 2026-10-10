import { useState } from 'react'
import { createPost } from '../api.js'
import { copyText } from '../utils.js'

const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn post', limit: 3000 },
  { id: 'x_thread', label: 'X thread', limit: 280 },
  { id: 'x_post', label: 'Single X post', limit: 280 },
]
const TONES = ['professional', 'casual', 'storytelling', 'educational', 'bold']
const LENGTHS = ['short', 'medium', 'long']

function Segmented({ label, options, value, onChange }) {
  return (
    <fieldset className="field">
      <legend>{label}</legend>
      <div className="segmented">
        {options.map((option) => {
          const id = option.id ?? option
          return (
            <button
              key={id}
              type="button"
              className={value === id ? 'seg active' : 'seg'}
              aria-pressed={value === id}
              onClick={() => onChange(id)}
            >
              {option.label ?? option}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}

function Counter({ length, limit }) {
  return <span className={length > limit ? 'counter over' : 'counter'}>{length.toLocaleString()} / {limit.toLocaleString()}</span>
}

export default function PostStudio({ videoId }) {
  const [options, setOptions] = useState({
    platform: 'linkedin',
    tone: 'professional',
    length: 'medium',
    emojis: false,
    hashtags: true,
    mention_source: true,
    instructions: '',
  })
  const [post, setPost] = useState(null) // { platform, text, tweets }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const set = (key) => (value) => setOptions((current) => ({ ...current, [key]: value }))
  const limit = PLATFORMS.find((p) => p.id === (post?.platform ?? options.platform)).limit

  async function generate() {
    setLoading(true)
    setError('')
    try {
      setPost(await createPost(videoId, options))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function copy() {
    const text = post.tweets ? post.tweets.join('\n\n') : post.text
    if (await copyText(text)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }

  function editTweet(index, value) {
    setPost((current) => ({ ...current, tweets: current.tweets.map((t, i) => (i === index ? value : t)) }))
  }

  return (
    <div className="studio">
      <div className="controls">
        <Segmented label="Platform" options={PLATFORMS} value={options.platform} onChange={set('platform')} />
        <Segmented label="Tone" options={TONES} value={options.tone} onChange={set('tone')} />
        <Segmented label="Length" options={LENGTHS} value={options.length} onChange={set('length')} />

        <div className="toggles">
          <label><input type="checkbox" checked={options.hashtags} onChange={(e) => set('hashtags')(e.target.checked)} /> Hashtags</label>
          <label><input type="checkbox" checked={options.emojis} onChange={(e) => set('emojis')(e.target.checked)} /> Emojis</label>
          <label><input type="checkbox" checked={options.mention_source} onChange={(e) => set('mention_source')(e.target.checked)} /> Credit the video</label>
        </div>

        <label className="field">
          <span className="legend">Extra instructions <span className="muted">(optional)</span></span>
          <input
            type="text"
            value={options.instructions}
            onChange={(e) => set('instructions')(e.target.value)}
            maxLength={500}
            placeholder="e.g. focus on the part about pricing, aim it at founders"
          />
        </label>

        <button className="btn btn-primary btn-wide" onClick={generate} disabled={loading}>
          {loading ? <><span className="spinner" /> Writing...</> : post ? 'Regenerate' : 'Generate post'}
        </button>
        {loading && !post && <p className="hint">The first post reads the whole video. Long videos take a little longer.</p>}
        {error && <p className="alert" role="alert">{error}</p>}
      </div>

      {post && (
        <div className={loading ? 'output dimmed' : 'output'}>
          <div className="output-head">
            <h2 className="card-title">Your {PLATFORMS.find((p) => p.id === post.platform).label}</h2>
            <button className="btn btn-ghost" onClick={copy}>{copied ? 'Copied!' : post.tweets ? 'Copy thread' : 'Copy'}</button>
          </div>

          {post.tweets ? (
            <ol className="thread">
              {post.tweets.map((tweet, index) => (
                <li key={index} className="tweet">
                  <textarea value={tweet} onChange={(e) => editTweet(index, e.target.value)} rows={4} aria-label={`Tweet ${index + 1}`} />
                  <Counter length={tweet.length} limit={limit} />
                </li>
              ))}
            </ol>
          ) : (
            <div className="single">
              <textarea
                value={post.text}
                onChange={(e) => setPost({ ...post, text: e.target.value })}
                rows={post.platform === 'linkedin' ? 16 : 5}
                aria-label="Generated post"
              />
              <Counter length={post.text.length} limit={limit} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
