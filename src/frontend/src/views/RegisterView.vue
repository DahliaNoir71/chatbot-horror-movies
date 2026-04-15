<script setup lang="ts">
import { ref, onMounted, type ComponentPublicInstance } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import axios from 'axios'
import { register } from '@/api/auth.api'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]{3,50}$/
const EMAIL_PATTERN = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/

const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')
const errors = ref<{
  username: string | null
  email: string | null
  password: string | null
}>({
  username: null,
  email: null,
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

  if (!email.value.trim()) {
    errors.value.email = "L'email est requis"
  } else if (!EMAIL_PATTERN.test(email.value.trim())) {
    errors.value.email = "L'email n'est pas valide"
  } else {
    errors.value.email = null
  }

  if (!password.value) {
    errors.value.password = 'Le mot de passe est requis'
  } else if (password.value.length < 7) {
    errors.value.password =
      'Le mot de passe doit contenir au moins 7 caractères'
  } else {
    errors.value.password = null
  }

  return !errors.value.username && !errors.value.email && !errors.value.password
}

async function handleSubmit() {
  apiError.value = null
  if (!validate()) return

  loading.value = true
  try {
    await register({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
    })
    await router.push({ name: 'login', query: { registered: 'true' } })
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        apiError.value =
          error.response.data?.detail ||
          "Ce nom d'utilisateur ou email est déjà pris"
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
          v-model="email"
          type="email"
          label="Email"
          :error="errors.email"
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

      <p class="text-center text-sm text-smoke-gray-500">
        <a href="/" class="hover:text-smoke-gray-300 underline">
          &larr; Retour à l'accueil
        </a>
      </p>
    </div>
  </div>
</template>
