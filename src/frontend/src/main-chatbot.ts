import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router/chatbot'
import { useAuthStore, setStoragePrefix } from '@/stores/auth.store'
import { setLoginUrl } from '@/api/auth-redirect'
import { setTokenKey } from '@/api/client'
import './style.css'
import AppChatbot from './AppChatbot.vue'

const app = createApp(AppChatbot)
app.use(createPinia())

setStoragePrefix('horrorbot_chat')
setTokenKey('horrorbot_chat_token')

const authStore = useAuthStore()
authStore.initFromStorage()
setLoginUrl('/chatbot.html#/login')

app.use(router)
app.mount('#app')
