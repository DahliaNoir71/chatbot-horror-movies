export interface Film {
  id: number
  tmdb_id: number
  title: string
  release_date: string | null
  vote_average: number | null
  popularity: number | null
  poster_path: string | null
}

export interface FilmDetail extends Film {
  imdb_id: string | null
  original_title: string | null
  overview: string | null
  runtime: number | null
  budget: number | null
  revenue: number | null
  vote_count: number | null
  tagline: string | null
  status: string | null
  original_language: string | null
}

export interface FilmSearchRequest {
  query: string
  limit?: number
}

export interface FilmSearchResult {
  id: number
  tmdb_id: number
  title: string
  overview: string | null
  release_date: string | null
  score: number
}

export interface FilmSearchResponse {
  query: string
  results: FilmSearchResult[]
  count: number
}

export interface PaginatedMeta {
  page: number
  size: number
  total: number
  pages: number
}

export interface PaginatedResponse<T> {
  data: T[]
  meta: PaginatedMeta
}
