export function formatDuration(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

function toSeconds(stamp) {
  return stamp.split(':').reduce((total, part) => total * 60 + Number(part), 0)
}

// Turns "[4:32]" citations into markdown links that open the video at that moment.
export function linkTimestamps(markdown, videoId) {
  return markdown.replace(/\[(\d{1,2}(?::\d{2}){1,2})\](?!\()/g, (match, stamp) => {
    return `[${stamp}](https://www.youtube.com/watch?v=${videoId}&t=${toSeconds(stamp)}s)`
  })
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
