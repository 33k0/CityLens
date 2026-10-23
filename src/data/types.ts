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
  pdf_page_start: number
  pdf_page_end: number
  pages_total: number
  pages_exhibit: number
  after_deadline: boolean | null
}

/** Channel families. Voice and Problems are never summed, ranked, or charted together. */
export type Family = 'voice' | 'problems'
export const FAMILY_OF: Record<RawComment['channel'] | '311', Family> = { letter: 'voice', email: 'voice', site: 'voice', '311': 'problems' }

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
