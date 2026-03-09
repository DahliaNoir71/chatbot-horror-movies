<script setup lang="ts">
import { ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

const emit = defineEmits<{
  clear: []
}>()

const showConfirm = ref(false)

function handleConfirm() {
  showConfirm.value = false
  emit('clear')
}
</script>

<template>
  <div>
    <BaseButton
      variant="ghost"
      size="sm"
      aria-label="Nouvelle conversation"
      @click="showConfirm = true"
    >
      Nouvelle conversation
    </BaseButton>

    <BaseModal
      :open="showConfirm"
      title="Effacer la conversation ?"
      @close="showConfirm = false"
    >
      <p class="text-smoke-gray-300 mb-6">
        Cette action supprimera tous les messages de la conversation en cours.
      </p>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" size="sm" @click="showConfirm = false">
          Annuler
        </BaseButton>
        <BaseButton variant="danger" size="sm" @click="handleConfirm">
          Effacer
        </BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
