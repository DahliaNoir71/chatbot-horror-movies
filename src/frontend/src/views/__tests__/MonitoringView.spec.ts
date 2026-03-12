import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MonitoringView from '../admin/MonitoringView.vue'

vi.stubEnv('VITE_GRAFANA_URL', 'http://localhost:3000')

function mountView() {
  return mount(MonitoringView, {
    global: {
      stubs: {
        LoadingSpinner: { template: '<div class="loading-spinner" />' },
      },
    },
  })
}

const TABS = [
  {
    id: 'api',
    label: 'API Overview',
    uid: 'horrorbot-api',
    slug: 'horrorbot-api',
  },
  {
    id: 'rag',
    label: 'RAG Performance',
    uid: 'horrorbot-rag',
    slug: 'horrorbot-rag',
  },
  { id: 'llm', label: 'LLM', uid: 'horrorbot-llm', slug: 'horrorbot-llm' },
  {
    id: 'infra',
    label: 'Infrastructure',
    uid: 'horrorbot-infra',
    slug: 'horrorbot-infra',
  },
]

function expectedSrc(uid: string, slug: string) {
  return `http://localhost:3000/d/${uid}/${slug}?orgId=1&theme=dark&kiosk`
}

describe('MonitoringView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('renders heading', () => {
      const wrapper = mountView()
      expect(wrapper.find('h1').text()).toBe('Monitoring')
    })

    it('renders 4 tabs', () => {
      const wrapper = mountView()
      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs).toHaveLength(4)
      expect(tabs[0]!.text()).toBe('API Overview')
      expect(tabs[1]!.text()).toBe('RAG Performance')
      expect(tabs[2]!.text()).toBe('LLM')
      expect(tabs[3]!.text()).toBe('Infrastructure')
    })

    it('first tab is active by default', () => {
      const wrapper = mountView()
      const firstTab = wrapper.find('[role="tab"]')
      expect(firstTab.attributes('aria-selected')).toBe('true')
    })

    it('renders iframe with correct src for default tab', () => {
      const wrapper = mountView()
      const iframe = wrapper.find('iframe')
      expect(iframe.exists()).toBe(true)
      expect(iframe.attributes('src')).toBe(
        expectedSrc('horrorbot-api', 'horrorbot-api')
      )
    })

    it('renders link to open Grafana directly', () => {
      const wrapper = mountView()
      const link = wrapper.find('a[target="_blank"]')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toBe('http://localhost:3000')
    })
  })

  describe('tab switching', () => {
    it.each(TABS.slice(1))(
      'switches to $label tab on click',
      async ({ id, uid, slug }) => {
        const wrapper = mountView()
        const tab = wrapper.find(`#tab-${id}`)
        await tab.trigger('click')
        expect(wrapper.find('iframe').attributes('src')).toBe(
          expectedSrc(uid, slug)
        )
      }
    )

    it('includes orgId=1, theme=dark, kiosk in iframe src', () => {
      const wrapper = mountView()
      const src = wrapper.find('iframe').attributes('src')!
      expect(src).toContain('orgId=1')
      expect(src).toContain('theme=dark')
      expect(src).toContain('kiosk')
    })
  })

  describe('loading state', () => {
    it('shows loading spinner initially', () => {
      const wrapper = mountView()
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })

    it('hides loading spinner after iframe load event', async () => {
      const wrapper = mountView()
      await wrapper.find('iframe').trigger('load')
      expect(wrapper.find('.loading-spinner').exists()).toBe(false)
    })

    it('shows loading spinner again on tab switch', async () => {
      const wrapper = mountView()
      await wrapper.find('iframe').trigger('load')
      expect(wrapper.find('.loading-spinner').exists()).toBe(false)

      await wrapper.find('#tab-rag').trigger('click')
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })
  })

  describe('error fallback', () => {
    it('shows error message on iframe error', async () => {
      const wrapper = mountView()
      await wrapper.find('iframe').trigger('error')
      expect(wrapper.text()).toContain(
        'Impossible de charger le tableau de bord'
      )
    })

    it('shows direct Grafana link on error', async () => {
      const wrapper = mountView()
      await wrapper.find('iframe').trigger('error')
      const errorLink = wrapper.find('a[href*="/d/horrorbot-api/"]')
      expect(errorLink.exists()).toBe(true)
      expect(errorLink.text()).toContain('Ouvrir directement dans Grafana')
    })

    it('resets error state on tab switch', async () => {
      const wrapper = mountView()
      await wrapper.find('iframe').trigger('error')
      expect(wrapper.text()).toContain('Impossible de charger')

      await wrapper.find('#tab-rag').trigger('click')
      expect(wrapper.text()).not.toContain('Impossible de charger')
    })
  })

  describe('keyboard navigation', () => {
    it('moves to next tab on ArrowRight', async () => {
      const wrapper = mountView()
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'ArrowRight' })
      expect(wrapper.find('#tab-rag').attributes('aria-selected')).toBe('true')
    })

    it('moves to previous tab on ArrowLeft', async () => {
      const wrapper = mountView()
      await wrapper.find('#tab-rag').trigger('click')
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'ArrowLeft' })
      expect(wrapper.find('#tab-api').attributes('aria-selected')).toBe('true')
    })

    it('wraps from last to first on ArrowRight', async () => {
      const wrapper = mountView()
      await wrapper.find('#tab-infra').trigger('click')
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'ArrowRight' })
      expect(wrapper.find('#tab-api').attributes('aria-selected')).toBe('true')
    })

    it('wraps from first to last on ArrowLeft', async () => {
      const wrapper = mountView()
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'ArrowLeft' })
      expect(wrapper.find('#tab-infra').attributes('aria-selected')).toBe(
        'true'
      )
    })

    it('moves to first tab on Home', async () => {
      const wrapper = mountView()
      await wrapper.find('#tab-llm').trigger('click')
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'Home' })
      expect(wrapper.find('#tab-api').attributes('aria-selected')).toBe('true')
    })

    it('moves to last tab on End', async () => {
      const wrapper = mountView()
      const tablist = wrapper.find('[role="tablist"]')
      await tablist.trigger('keydown', { key: 'End' })
      expect(wrapper.find('#tab-infra').attributes('aria-selected')).toBe(
        'true'
      )
    })
  })

  describe('accessibility', () => {
    it('iframe has descriptive title attribute', () => {
      const wrapper = mountView()
      expect(wrapper.find('iframe').attributes('title')).toBe(
        'Tableau de bord Grafana : API Overview'
      )
    })

    it('active tab has aria-selected true', () => {
      const wrapper = mountView()
      const activeTab = wrapper.find('[role="tab"][aria-selected="true"]')
      expect(activeTab.text()).toBe('API Overview')
    })

    it('inactive tabs have aria-selected false', () => {
      const wrapper = mountView()
      const inactiveTabs = wrapper.findAll(
        '[role="tab"][aria-selected="false"]'
      )
      expect(inactiveTabs).toHaveLength(3)
    })

    it('tabs have aria-controls linking to panels', () => {
      const wrapper = mountView()
      const tabs = wrapper.findAll('[role="tab"]')
      tabs.forEach((tab) => {
        const id = tab.attributes('id')!.replace('tab-', '')
        expect(tab.attributes('aria-controls')).toBe(`panel-${id}`)
      })
    })

    it('panels have aria-labelledby linking to tabs', () => {
      const wrapper = mountView()
      const panels = wrapper.findAll('[role="tabpanel"]')
      panels.forEach((panel) => {
        const id = panel.attributes('id')!.replace('panel-', '')
        expect(panel.attributes('aria-labelledby')).toBe(`tab-${id}`)
      })
    })

    it('tablist has aria-label', () => {
      const wrapper = mountView()
      expect(wrapper.find('[role="tablist"]').attributes('aria-label')).toBe(
        'Tableaux de bord Grafana'
      )
    })

    it('active tab has tabindex 0', () => {
      const wrapper = mountView()
      const activeTab = wrapper.find('[role="tab"][aria-selected="true"]')
      expect(activeTab.attributes('tabindex')).toBe('0')
    })

    it('inactive tabs have tabindex -1', () => {
      const wrapper = mountView()
      const inactiveTabs = wrapper.findAll(
        '[role="tab"][aria-selected="false"]'
      )
      inactiveTabs.forEach((tab) => {
        expect(tab.attributes('tabindex')).toBe('-1')
      })
    })
  })
})
