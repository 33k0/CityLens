export type Stance = 'support' | 'oppose' | 'neutral' | 'unclear'

/** One public comment, PII-free. Milestone 1 shape (ingest only); later milestones add
 *  category / tract / weights per the data model in the prompt. */
export interface RawComment {
  comment_id: string
  item: string
  item_id: string
  item_title: string
  meeting_id: string
  meeting_date: string
  channel: 'ecomment' | 'email'
  mock: boolean
  received_at: string
  posted_raw: string
  stance: Stance
  stance_source: 'self_reported' | 'llm' | 'rule'
  neighborhood: string
  zip: string
  text: string
  source_url: string
  ecomment_id: string
  duplicate_of: string | null
}

export interface ItemMeta {
  item: string
  item_id: string
  item_title: string
  meeting_id: string
  meeting_date: string
  declared_count: number
  scraped_count: number
  exact_duplicates: number
  source_url: string
  scraped_at: string
}

export interface CommentsRawPayload {
  generated_at: string
  source: string
  items: ItemMeta[]
  comments: RawComment[]
}
