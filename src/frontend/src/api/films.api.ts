import apiClient from './client'
import type {
  Film,
  FilmDetail,
  FilmSearchRequest,
  FilmSearchResponse,
  PaginatedResponse,
} from '@/types'

export function listFilms(
  page = 1,
  size = 20
): Promise<PaginatedResponse<Film>> {
  return apiClient
    .get<PaginatedResponse<Film>>('/films', { params: { page, size } })
    .then((r) => r.data)
}

export function getFilmById(id: number): Promise<FilmDetail> {
  return apiClient.get<FilmDetail>(`/films/${id}`).then((r) => r.data)
}

export function searchFilms(
  request: FilmSearchRequest
): Promise<FilmSearchResponse> {
  return apiClient
    .post<FilmSearchResponse>('/films/search', request)
    .then((r) => r.data)
}
