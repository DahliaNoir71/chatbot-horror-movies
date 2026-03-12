<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

interface DashboardTab {
  id: string
  label: string
  uid: string
  slug: string
}

const DASHBOARD_TABS: DashboardTab[] = [
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

const grafanaUrl =
  (import.meta.env.VITE_GRAFANA_URL as string | undefined) ??
  'http://localhost:3000'
const activeTab = ref(DASHBOARD_TABS[0]!.id)
const iframeLoading = ref(true)
const iframeError = ref(false)

const activeIframeSrc = computed(() => {
  const tab = DASHBOARD_TABS.find((t) => t.id === activeTab.value)
  if (!tab) return ''
  return `${grafanaUrl}/d/${tab.uid}/${tab.slug}?orgId=1&theme=dark&kiosk`
})

function selectTab(tabId: string) {
  if (tabId === activeTab.value) return
  activeTab.value = tabId
  iframeLoading.value = true
  iframeError.value = false
}

function onIframeLoad() {
  iframeLoading.value = false
}

function onIframeError() {
  iframeLoading.value = false
  iframeError.value = true
}

function onTabKeydown(event: KeyboardEvent) {
  const currentIndex = DASHBOARD_TABS.findIndex((t) => t.id === activeTab.value)
  let newIndex = currentIndex

  if (event.key === 'ArrowRight') {
    newIndex = (currentIndex + 1) % DASHBOARD_TABS.length
  } else if (event.key === 'ArrowLeft') {
    newIndex =
      (currentIndex - 1 + DASHBOARD_TABS.length) % DASHBOARD_TABS.length
  } else if (event.key === 'Home') {
    newIndex = 0
  } else if (event.key === 'End') {
    newIndex = DASHBOARD_TABS.length - 1
  } else {
    return
  }

  event.preventDefault()
  const newTab = DASHBOARD_TABS[newIndex]!
  selectTab(newTab.id)

  nextTick(() => {
    document.getElementById(`tab-${newTab.id}`)?.focus()
  })
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between px-6 pt-6 pb-4">
      <h1 class="text-2xl font-bold text-smoke-gray-100">Monitoring</h1>
      <a
        :href="grafanaUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="text-sm text-smoke-gray-400 hover:text-blood-red-400 transition-colors"
      >
        Ouvrir Grafana &#x2197;
      </a>
    </div>

    <div
      role="tablist"
      aria-label="Tableaux de bord Grafana"
      class="flex gap-1 px-6 border-b border-deep-black-700"
      @keydown="onTabKeydown"
    >
      <button
        v-for="tab in DASHBOARD_TABS"
        :id="`tab-${tab.id}`"
        :key="tab.id"
        role="tab"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`panel-${tab.id}`"
        :tabindex="activeTab === tab.id ? 0 : -1"
        class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="
          activeTab === tab.id
            ? 'border-blood-red-500 text-blood-red-400'
            : 'border-transparent text-smoke-gray-400 hover:text-smoke-gray-200 hover:border-smoke-gray-600'
        "
        @click="selectTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div
      v-for="tab in DASHBOARD_TABS"
      :id="`panel-${tab.id}`"
      :key="tab.id"
      role="tabpanel"
      :aria-labelledby="`tab-${tab.id}`"
      :hidden="activeTab !== tab.id || undefined"
      class="flex-1 relative min-h-[600px]"
    >
      <template v-if="activeTab === tab.id">
        <div
          v-if="iframeLoading"
          class="absolute inset-0 flex items-center justify-center bg-deep-black-900/80 z-10"
        >
          <LoadingSpinner size="lg" />
        </div>

        <div
          v-if="iframeError"
          class="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-deep-black-900 z-10"
        >
          <p class="text-smoke-gray-400">
            Impossible de charger le tableau de bord.
          </p>
          <a
            :href="`${grafanaUrl}/d/${tab.uid}/${tab.slug}`"
            target="_blank"
            rel="noopener noreferrer"
            class="text-blood-red-400 hover:text-blood-red-300 underline transition-colors"
          >
            Ouvrir directement dans Grafana
          </a>
        </div>

        <iframe
          :src="activeIframeSrc"
          :title="`Tableau de bord Grafana : ${tab.label}`"
          class="w-full h-full border-0"
          allow="fullscreen"
          loading="lazy"
          @load="onIframeLoad"
          @error="onIframeError"
        />
      </template>
    </div>
  </div>
</template>
