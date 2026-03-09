<script setup lang="ts">
import { ref, onMounted, type ComponentPublicInstance } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import axios from 'axios'
import { register } from '@/api/auth.api'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]{3,50}$/

const router = useRouter()

const username = ref('')
const password = ref('')
const errors = ref<{ username: string | null; password: string | null }>({
  username: null,
  password: null,
})
const apiError = ref<string | null>(null)
const loading = ref(false)
const usernameInput = ref<ComponentPublicInstance | null>(null)

function validate(): boolean {
  if (!username.value.trim()) {
    errors.value.username = "Le nom d'utilisateur est requis"
  } else if (!USERNAME_PATTERN.test(username.value.trim())) {
    errors.value.username =
      "Le nom d'utilisateur doit contenir entre 3 et 50 caractères (lettres, chiffres, _ ou -)"
  } else {
    errors.value.username = null
  }

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
    await register({
      username: username.value.trim(),
      password: password.value,
    })
    await router.push({ name: 'login', query: { registered: 'true' } })
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        apiError.value = "Ce nom d'utilisateur est déjà pris"
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
        Inscription
      </h1>

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
          Créer un compte
        </BaseButton>
      </form>

      <p class="text-center text-sm text-smoke-gray-400">
        Déjà un compte ?
        <RouterLink
          :to="{ name: 'login' }"
          class="text-blood-red-400 hover:text-blood-red-300 underline"
        >
          Se connecter
        </RouterLink>
      </p>
    </div>
  </div>
</template>
