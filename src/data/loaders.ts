import type { CommentsRawPayload } from './types'

const base = import.meta.env.BASE_URL.replace(/\/$/, '')

export async function loadCommentsRaw(): Promise<CommentsRawPayload> {
  const tryUrls = [`${base}/data/comments_raw.json`, `${base}/data/fixtures/ecomments.json`]
  let lastErr: unknown
  for (const url of tryUrls) {
    try {
      const r = await fetch(url)
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
      return (await r.json()) as CommentsRawPayload
    } catch (e) {
      lastErr = e
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('could not load comments')
}
