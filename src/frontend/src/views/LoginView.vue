<script setup lang="ts">
import { ref, computed, onMounted, type ComponentPublicInstance } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth.store'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const hasRegisterRoute = computed(() =>
  router.getRoutes().some((r) => r.name === 'register')
)

const username = ref('')
const password = ref('')
const errors = ref<{ username: string | null; password: string | null }>({
  username: null,
  password: null,
})
const apiError = ref<string | null>(null)
const loading = ref(false)
const usernameInput = ref<ComponentPublicInstance | null>(null)

const successMessage = computed(() =>
  route.query.registered === 'true'
    ? 'Compte créé avec succès. Vous pouvez maintenant vous connecter.'
    : null
)

function validate(): boolean {
  errors.value.username = !username.value.trim()
    ? "Le nom d'utilisateur est requis"
    : null

  if (!password.value) {
    errors.value.password = 'Le mot de passe est requis'
  } else if (password.value.length < 8) {
    errors.value.password =
      'Le mot de passe doit contenir au moins 8 caractères'
  } else {
    errors.value.password = null
  }

  return !errors.value.username && !errors.value.password
}

async function handleSubmit() {
  apiError.value = null
  if (!validate()) return

  loading.value = true
  try {
    await authStore.login({
      username: username.value.trim(),
      password: password.value,
    })
    const redirect =
      typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        apiError.value = 'Identifiants invalides'
      } else if (!error.response) {
        apiError.value = 'Erreur de connexion au serveur'
      } else {
        apiError.value = 'Une erreur est survenue'
      }
    } else {
      apiError.value = 'Une erreur est survenue'
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  usernameInput.value?.$el?.querySelector('input')?.focus()
})
</script>

<template>
  <div class="min-h-full flex items-center justify-center px-4 py-12">
    <div
      class="w-full max-w-md space-y-6 bg-deep-black-800 p-8 rounded-xl shadow-lg border border-smoke-gray-700"
    >
      <h1 class="text-2xl font-bold text-center text-smoke-gray-100">
        Connexion
      </h1>

      <output
        v-if="successMessage"
        class="block rounded-lg border border-smoke-gray-500 bg-deep-black-700 p-4 text-smoke-gray-200"
      >
        {{ successMessage }}
      </output>

      <ErrorAlert
        v-if="apiError"
        :message="apiError"
        dismissible
        @dismiss="apiError = null"
      />

      <form novalidate class="space-y-5" @submit.prevent="handleSubmit">
        <BaseInput
          ref="usernameInput"
          v-model="username"
          label="Nom d'utilisateur"
          :error="errors.username"
          required
        />

        <BaseInput
          v-model="password"
          type="password"
          label="Mot de passe"
          :error="errors.password"
          required
        />

        <BaseButton type="submit" :loading="loading" class="w-full" size="lg">
          Se connecter
        </BaseButton>
      </form>

      <p
        v-if="hasRegisterRoute"
        class="text-center text-sm text-smoke-gray-400"
      >
        Pas encore de compte ?
        <RouterLink
          :to="{ name: 'register' }"
          class="text-blood-red-400 hover:text-blood-red-300 underline"
        >
          Créer un compte
        </RouterLink>
      </p>
    </div>
  </div>
</template>
