export type Stance = 'support' | 'oppose' | 'neutral' | 'unclear'
export type CommenterType = 'resident' | 'organization' | 'developer_or_counsel' | 'government'

export interface RawComment {
  comment_id: string
  item: string
  item_id: string
  item_title: string
  meeting_id: string
  meeting_date: string
  channel: 'letter' | 'email' | 'site'
  mock: boolean
  received_at: string
  posted_raw: string
  stance: Stance
  stance_source: 'self_reported' | 'llm' | 'rule' | 'pending_llm'
  neighborhood: string
  zip: string
  text: string
  source_url: string
  subject: string
  language: string
  commenter_type: CommenterType
  identity_hash: string
  duplicate_of: string | null
  ocr: boolean
  has_address_hint: boolean
  pdf_file: string
  tract_id?: string | null // set by resolve_locations.py (Milestone 4)
  pdf_page_start: number
  pdf_page_end: number
  pages_total: number
  pages_exhibit: number
  after_deadline: boolean | null
}

export interface ItemMeta {
  item: string
  item_id: string
  item_title: string
  meeting_id: string
  meeting_date: string
  agenda_number: string | null
  priority: boolean
  source_url: string
  attachment_url: string
  pages: number
  ocr_pages: number
  ocr_missing_pages: number
  letters: number
  exhibit_pages: number
  pages_unattributed: number
  exact_duplicates: number
  organizations: number
  letters_by_type: Partial<Record<CommenterType, number>>
  pages_by_type: Partial<Record<CommenterType, number>>
  pages_summary: string
  pdfs?: string[]
  attachments?: unknown[]
  after_deadline: number | null
  comment_deadline: string | null
}

export interface CommentsRawPayload {
  generated_at: string
  source: string
  items: ItemMeta[]
  comments: RawComment[]
}

/** Joined voice record from public/data/comments.json (export_comments.py). Voice family only. */
export interface VoiceComment {
  comment_id: string
  item: string
  item_title: string
  meeting_date: string
  channel: 'letter' | 'email' | 'site'
  mock: boolean
  family: 'voice'
  received_at: string
  subject: string
  text: string
  language: string
  commenter_type: CommenterType
  duplicate_of: string | null
  campaign_id: string | null
  after_deadline: boolean | null
  source_url: string
  submitted_via: string
  to_office: string
  ocr: boolean
  pdf_page_start: number | null
  pdf_page_end: number | null
  pages_total: number | null
  pages_exhibit: number | null
  tract_id: string | null
  location_precision: 'address' | 'neighborhood' | 'zip' | 'none' | string
  location_source?: string
  multi_tract: boolean
  council_district: number | null
  matched_name?: string
  category: string
  confidence: number | null
  evidence_quote: string
  stance: Stance
  stance_source: string
  stance_evidence: string
  engine: string
}

export interface VoiceItem {
  item: string
  title: string
  meeting_date: string
  mock: boolean
  source: string
  source_url: string | null
  pages_summary: string | null
  count: number
  count_unique: number
  channels: string[]
}

export interface VoicePayload {
  generated_at: string
  family: 'voice'
  note: string
  categories: { key: string; label: string; description: string }[]
  campaigns: unknown
  channels: Record<string, { count: number; mock: boolean; precision: Record<string, number> }>
  items: VoiceItem[]
  comments: VoiceComment[]
}

export interface InboxEmail {
  comment_id: string
  mock: true
  received_at: string
  from: string
  to: string
  subject: string
  body: string
  language: string
  submitted_via: string
  item: string
  item_title: string
  attachments: { file: string; kind: string; description?: string; redacted: boolean; served: boolean }[]
}
