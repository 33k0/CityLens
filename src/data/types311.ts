export interface Requests311ByTract {
  source: string
  real: true
  since: string
  generated_at: string
  rows_total: number
  rows_located: number
  categories: string[]
  taxonomy: { service_type: string; category_raw: string; category: string }[]
  months: string[]
  months_covered: number
  totals: Record<string, number>
  rate_per_1k_annualized: Record<string, number>
  population: Record<string, number>
  by_tract: Record<string, Record<string, Record<string, number>>> // tract -> category -> YYYY-MM -> n
}

export interface Request311Sample {
  real: true
  note: string
  rows: { request_id: string; month: string; category_raw: string; subcategory_raw: string | null; category: string; status: string; source: string; tract_id: string; council_district: number | null }[]
}
