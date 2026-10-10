import { formatDuration } from '../utils.js'

export default function VideoCard({ video }) {
  const url = `https://www.youtube.com/watch?v=${video.video_id}`
  return (
    <div className="card video-card">
      <a href={url} target="_blank" rel="noreferrer" className="thumb">
        <img src={video.thumbnail} alt="" />
        {video.duration_seconds > 0 && <span className="duration">{formatDuration(video.duration_seconds)}</span>}
      </a>
      <div className="video-meta">
        <a href={url} target="_blank" rel="noreferrer" className="video-title">
          {video.title}
        </a>
        {video.author && <div className="muted">{video.author}</div>}
        <div className="badges">
          <span className="badge" title={video.source === 'whisper' ? 'No captions: transcribed from the audio with Whisper' : 'From YouTube captions'}>
            {video.source === 'whisper' ? 'Whisper transcript' : 'Captions'}
          </span>
          <span className="badge">{video.language.toUpperCase()}</span>
          <span className="badge">{video.word_count.toLocaleString()} words</span>
        </div>
      </div>
    </div>
  )
}
