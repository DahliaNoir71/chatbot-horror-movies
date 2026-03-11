<script setup lang="ts">
import { ref, onMounted, type ComponentPublicInstance } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth.store'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const errors = ref<{ email: string | null; password: string | null }>({
  email: null,
  password: null,
})
const apiError = ref<string | null>(null)
const loading = ref(false)
const emailInput = ref<ComponentPublicInstance | null>(null)

function validate(): boolean {
  errors.value.email = !email.value.trim() ? "L'email est requis" : null

  if (!password.value) {
    errors.value.password = 'Le mot de passe est requis'
  } else if (password.value.length < 8) {
    errors.value.password =
      'Le mot de passe doit contenir au moins 8 caractères'
  } else {
    errors.value.password = null
  }

  return !errors.value.email && !errors.value.password
}

async function handleSubmit() {
  apiError.value = null
  if (!validate()) return

  loading.value = true
  try {
    await authStore.loginAsAdmin({
      email: email.value.trim(),
      password: password.value,
    })
    await router.push('/dashboard')
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
  emailInput.value?.$el?.querySelector('input')?.focus()
})
</script>

<template>
  <div class="min-h-full flex items-center justify-center px-4 py-12">
    <div
      class="w-full max-w-md space-y-6 bg-deep-black-800 p-8 rounded-xl shadow-lg border border-smoke-gray-700"
    >
      <h1 class="text-2xl font-bold text-center text-smoke-gray-100">
        Connexion Admin
      </h1>

      <ErrorAlert
        v-if="apiError"
        :message="apiError"
        dismissible
        @dismiss="apiError = null"
      />

      <form novalidate class="space-y-5" @submit.prevent="handleSubmit">
        <BaseInput
          ref="emailInput"
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
          Se connecter
        </BaseButton>
      </form>

      <p class="text-center text-sm text-smoke-gray-500">
        <a href="/" class="hover:text-smoke-gray-300 underline">
          &larr; Retour à l'accueil
        </a>
      </p>
    </div>
  </div>
</template>
