import { useState } from 'react'
import { getInsights, processVideo } from './api.js'
import UrlForm from './components/UrlForm.jsx'
import VideoCard from './components/VideoCard.jsx'
import Insights from './components/Insights.jsx'
import PostStudio from './components/PostStudio.jsx'
import Chat from './components/Chat.jsx'

const TABS = [
  { id: 'post', label: 'Create post' },
  { id: 'chat', label: 'Chat with video' },
]

export default function App() {
  const [video, setVideo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [insights, setInsights] = useState({ status: 'idle', data: null, error: '' })
  const [tab, setTab] = useState('post')

  async function handleSubmit(url) {
    setLoading(true)
    setError('')
    try {
      const info = await processVideo(url)
      setVideo(info)
      setTab('post')
      loadInsights(info.video_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadInsights(videoId) {
    setInsights({ status: 'loading', data: null, error: '' })
    try {
      setInsights({ status: 'ready', data: await getInsights(videoId), error: '' })
    } catch (err) {
      setInsights({ status: 'error', data: null, error: err.message })
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Vid2Post
        </div>
      </header>

      <main className="main">
        <section className={video ? 'hero hero-compact' : 'hero'}>
          {!video && (
            <>
              <h1>Turn any YouTube video into a post people actually read.</h1>
              <p className="lede">
                Paste a link to get a LinkedIn post or X thread written from the full transcript, then chat with
                the video to dig deeper.
              </p>
            </>
          )}
          <UrlForm onSubmit={handleSubmit} loading={loading} />
          {loading && <p className="hint">Fetching the transcript. Videos without captions are transcribed from audio, which can take a minute.</p>}
          {error && <p className="alert" role="alert">{error}</p>}
        </section>

        {video && (
          <div className="workspace" key={video.video_id}>
            <aside className="sidebar">
              <VideoCard video={video} />
              <Insights state={insights} onRetry={() => loadInsights(video.video_id)} />
            </aside>

            <section className="panel">
              <div className="tabs" role="tablist">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    role="tab"
                    aria-selected={tab === t.id}
                    className={tab === t.id ? 'tab active' : 'tab'}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              {/* Both stay mounted so switching tabs keeps the draft and the conversation. */}
              <div hidden={tab !== 'post'}>
                <PostStudio videoId={video.video_id} />
              </div>
              <div hidden={tab !== 'chat'}>
                <Chat videoId={video.video_id} suggestions={insights.data?.suggested_questions ?? []} />
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}
