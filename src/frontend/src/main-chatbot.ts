import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router/chatbot'
import { useAuthStore } from '@/stores/auth.store'
import './style.css'
import AppChatbot from './AppChatbot.vue'

const app = createApp(AppChatbot)
app.use(createPinia())

const authStore = useAuthStore()
authStore.initFromStorage()

app.use(router)
app.mount('#app')
