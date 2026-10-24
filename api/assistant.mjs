// Vercel serverless endpoint for the staff chat: POST /api/assistant -> the same handler the dev server uses
// (server/assistant.mjs), which runs IBM Bob from the official bobshell package installed as a dependency.
// Needs BOB_API_KEY and BOB_LICENSE_ACCEPTED=true in the Vercel project's environment variables.
import { handle } from '../server/assistant.mjs'

export const config = { maxDuration: 60 }

export default async function assistant(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' })
  let body = req.body
  if (typeof body === 'string') { try { body = JSON.parse(body || '{}') } catch { return res.status(400).json({ error: 'invalid JSON' }) } }
  try {
    const out = await handle(body || {})
    res.status(out.status).json(out.body)
  } catch (e) {
    console.error('[assistant] error:', String(e?.message || e))
    res.status(500).json({ error: 'internal error' })
  }
}
