<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getHealth } from '@/api/health.api'
import type { HealthResponse } from '@/types'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const health = ref<HealthResponse | null>(null)
const loading = ref(false)
const error = ref('')

async function fetchHealth() {
  loading.value = true
  error.value = ''
  try {
    health.value = await getHealth()
  } catch {
    error.value = 'Impossible de récupérer le statut du système.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchHealth)

function componentStatus(ok: boolean | undefined): string {
  return ok ? 'Opérationnel' : 'Indisponible'
}

function statusClass(ok: boolean | undefined): string {
  return ok ? 'text-green-400' : 'text-blood-red-400'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-smoke-gray-100">Tableau de bord</h1>
      <BaseButton
        variant="secondary"
        size="sm"
        :loading="loading"
        :disabled="loading"
        @click="fetchHealth"
      >
        Rafraîchir
      </BaseButton>
    </div>

    <div v-if="loading && !health" class="flex justify-center py-12">
      <LoadingSpinner size="lg" />
    </div>

    <ErrorAlert
      v-else-if="error"
      :message="error"
      dismissible
      @dismiss="error = ''"
    />

    <template v-else-if="health">
      <div class="flex items-center gap-3 bg-deep-black-700 rounded-lg p-4">
        <span
          class="inline-block h-3 w-3 rounded-full"
          :class="
            health.status === 'healthy' ? 'bg-green-400' : 'bg-blood-red-400'
          "
        />
        <span class="text-smoke-gray-100 font-semibold">
          {{
            health.status === 'healthy'
              ? 'Système opérationnel'
              : 'Système dégradé'
          }}
        </span>
        <span class="ml-auto text-sm text-smoke-gray-400">
          v{{ health.version }}
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- LLM -->
        <div class="bg-deep-black-700 rounded-lg p-5 space-y-2">
          <h2
            class="text-sm font-medium text-smoke-gray-400 uppercase tracking-wide"
          >
            LLM
          </h2>
          <p
            :class="statusClass(health.components.llm.loaded)"
            class="text-lg font-semibold"
          >
            {{ componentStatus(health.components.llm.loaded) }}
          </p>
          <p
            v-if="health.components.llm.memory_mb != null"
            class="text-sm text-smoke-gray-400"
          >
            Mémoire : {{ health.components.llm.memory_mb }} Mo
          </p>
        </div>

        <!-- Database -->
        <div class="bg-deep-black-700 rounded-lg p-5 space-y-2">
          <h2
            class="text-sm font-medium text-smoke-gray-400 uppercase tracking-wide"
          >
            Base de données
          </h2>
          <p
            :class="statusClass(health.components.database.connected)"
            class="text-lg font-semibold"
          >
            {{ componentStatus(health.components.database.connected) }}
          </p>
          <p
            v-if="health.components.database.pool_available != null"
            class="text-sm text-smoke-gray-400"
          >
            Connexions disponibles :
            {{ health.components.database.pool_available }}
          </p>
        </div>

        <!-- Embeddings -->
        <div class="bg-deep-black-700 rounded-lg p-5 space-y-2">
          <h2
            class="text-sm font-medium text-smoke-gray-400 uppercase tracking-wide"
          >
            Embeddings
          </h2>
          <p
            :class="statusClass(health.components.embeddings.model_loaded)"
            class="text-lg font-semibold"
          >
            {{ componentStatus(health.components.embeddings.model_loaded) }}
          </p>
        </div>
      </div>

      <p class="text-xs text-smoke-gray-500">
        Dernière vérification :
        {{ new Date(health.timestamp).toLocaleString('fr-FR') }}
      </p>
    </template>
  </div>
</template>
