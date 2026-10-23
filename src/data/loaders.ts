import type { CommentsRawPayload } from './types'

const base = import.meta.env.BASE_URL.replace(/\/$/, '')

export async function loadCommentsRaw(): Promise<CommentsRawPayload> {
  const tryUrls = [`${base}/data/comments_raw.json`, `${base}/data/fixtures/letters.json`]
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

import type { Requests311ByTract, Request311Sample } from './types311'

async function getJson<T>(urls: string[]): Promise<T> {
  let lastErr: unknown
  for (const url of urls) {
    try {
      const r = await fetch(url)
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
      return (await r.json()) as T
    } catch (e) {
      lastErr = e
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('load failed')
}

export const load311ByTract = () => getJson<Requests311ByTract>([`${base}/data/requests_311_by_tract.json`, `${base}/data/fixtures/requests_311_by_tract.json`])
export const load311Sample = () => getJson<Request311Sample>([`${base}/data/requests_311_sample.json`])
