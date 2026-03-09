import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'
import FilmsView from '../admin/FilmsView.vue'
import type { Film, PaginatedResponse, FilmSearchResult } from '@/types'

vi.mock('@/api/films.api', () => ({
  listFilms: vi.fn(),
  searchFilms: vi.fn(),
}))

import { listFilms, searchFilms } from '@/api/films.api'

const FilmSearchStub = defineComponent({
  name: 'FilmSearch',
  emits: ['search'],
  template: '<div class="film-search" />',
})

function makeFilm(id: number): Film {
  return {
    id,
    tmdb_id: id * 10,
    title: `Film ${id}`,
    release_date: '2024-01-01',
    vote_average: 7.5,
    popularity: 100,
    poster_path: null,
  }
}

function makePaginatedResponse(
  films: Film[],
  page = 1,
  pages = 1,
  total?: number
): PaginatedResponse<Film> {
  return {
    data: films,
    meta: { page, size: 20, total: total ?? films.length, pages },
  }
}

function makeSearchResult(id: number): FilmSearchResult {
  return {
    id,
    tmdb_id: id * 10,
    title: `Result ${id}`,
    overview: `Overview ${id}`,
    release_date: '2024-06-15',
    score: 0.85,
  }
}

function mountFilms() {
  return mount(FilmsView, {
    global: {
      stubs: {
        FilmCard: { template: '<div class="film-card" />', props: ['film'] },
        FilmSearch: FilmSearchStub,
        LoadingSpinner: { template: '<div class="loading-spinner" />' },
        ErrorAlert: {
          template: '<div class="error-alert" />',
          props: ['message', 'dismissible'],
          emits: ['dismiss'],
        },
        BaseButton: {
          template:
            '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['variant', 'size', 'disabled'],
          emits: ['click'],
        },
        RouterLink: { template: '<a><slot /></a>', props: ['to'] },
      },
    },
  })
}

describe('FilmsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('initial load', () => {
    it('renders heading and calls listFilms on mount', async () => {
      const films = [makeFilm(1), makeFilm(2)]
      vi.mocked(listFilms).mockResolvedValue(makePaginatedResponse(films))

      const wrapper = mountFilms()
      await flushPromises()

      expect(wrapper.find('h1').text()).toBe('Films')
      expect(listFilms).toHaveBeenCalledWith(1, 20)
      expect(wrapper.findAll('.film-card')).toHaveLength(2)
    })

    it('shows loading spinner while loading', async () => {
      vi.mocked(listFilms).mockReturnValue(new Promise(() => {}))

      const wrapper = mountFilms()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })

    it('shows error message on load failure', async () => {
      vi.mocked(listFilms).mockRejectedValue(new Error('Network error'))

      const wrapper = mountFilms()
      await flushPromises()

      expect(wrapper.find('.error-alert').exists()).toBe(true)
    })

    it('shows empty state when no films', async () => {
      vi.mocked(listFilms).mockResolvedValue(makePaginatedResponse([]))

      const wrapper = mountFilms()
      await flushPromises()

      expect(wrapper.text()).toContain('Aucun film disponible')
    })
  })

  describe('search', () => {
    it('calls searchFilms and shows results count', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)])
      )
      const results: FilmSearchResult[] = [
        makeSearchResult(1),
        makeSearchResult(2),
      ]
      vi.mocked(searchFilms).mockResolvedValue({
        query: 'horror',
        results,
        count: 2,
      })

      const wrapper = mountFilms()
      await flushPromises()

      const filmSearch = wrapper.findComponent(FilmSearchStub)
      filmSearch.vm.$emit('search', 'horror')
      await flushPromises()

      expect(searchFilms).toHaveBeenCalledWith({ query: 'horror' })
      expect(wrapper.text()).toContain('2 résultat(s)')
      expect(wrapper.text()).toContain('horror')
    })

    it('returns to browse mode on empty query', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)])
      )
      vi.mocked(searchFilms).mockResolvedValue({
        query: 'test',
        results: [makeSearchResult(1)],
        count: 1,
      })

      const wrapper = mountFilms()
      await flushPromises()

      const filmSearch = wrapper.findComponent(FilmSearchStub)

      // Enter search mode
      filmSearch.vm.$emit('search', 'test')
      await flushPromises()
      expect(searchFilms).toHaveBeenCalled()

      // Clear search
      filmSearch.vm.$emit('search', '')
      await flushPromises()

      // Back to browse mode: FilmCard should be rendered
      expect(wrapper.findAll('.film-card')).toHaveLength(1)
    })

    it('shows "Aucun résultat" when search returns empty', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)])
      )
      vi.mocked(searchFilms).mockResolvedValue({
        query: 'nonexistent',
        results: [],
        count: 0,
      })

      const wrapper = mountFilms()
      await flushPromises()

      const filmSearch = wrapper.findComponent(FilmSearchStub)
      filmSearch.vm.$emit('search', 'nonexistent')
      await flushPromises()

      expect(wrapper.text()).toContain('Aucun résultat trouvé')
    })

    it('shows error on search failure', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)])
      )
      vi.mocked(searchFilms).mockRejectedValue(new Error('Search failed'))

      const wrapper = mountFilms()
      await flushPromises()

      const filmSearch = wrapper.findComponent(FilmSearchStub)
      filmSearch.vm.$emit('search', 'horror')
      await flushPromises()

      expect(wrapper.find('.error-alert').exists()).toBe(true)
    })
  })

  describe('pagination', () => {
    it('shows pagination when multiple pages', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)], 1, 3, 60)
      )

      const wrapper = mountFilms()
      await flushPromises()

      expect(wrapper.text()).toContain('Page 1 / 3')
      expect(wrapper.text()).toContain('Précédent')
      expect(wrapper.text()).toContain('Suivant')
    })

    it('hides pagination for single page', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)], 1, 1, 1)
      )

      const wrapper = mountFilms()
      await flushPromises()

      expect(wrapper.text()).not.toContain('Précédent')
    })

    it('disables Précédent on first page', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)], 1, 3, 60)
      )

      const wrapper = mountFilms()
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const prevButton = buttons.find((b) => b.text().includes('Précédent'))
      expect(prevButton?.attributes('disabled')).toBeDefined()
    })

    it('disables Suivant on last page', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)], 3, 3, 60)
      )

      const wrapper = mountFilms()
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const nextButton = buttons.find((b) => b.text().includes('Suivant'))
      expect(nextButton?.attributes('disabled')).toBeDefined()
    })

    it('loads next page on Suivant click', async () => {
      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(1)], 1, 3, 60)
      )

      const wrapper = mountFilms()
      await flushPromises()

      vi.mocked(listFilms).mockResolvedValue(
        makePaginatedResponse([makeFilm(2)], 2, 3, 60)
      )

      const buttons = wrapper.findAll('button')
      const nextButton = buttons.find((b) => b.text().includes('Suivant'))
      await nextButton?.trigger('click')
      await flushPromises()

      expect(listFilms).toHaveBeenCalledWith(2, 20)
      expect(wrapper.text()).toContain('Page 2 / 3')
    })
  })
})
