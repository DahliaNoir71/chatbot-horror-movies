import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import { useAuthStore } from '@/stores/auth.store'
import './style.css'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())

const authStore = useAuthStore()
authStore.initFromStorage()

app.use(router)
app.mount('#app')
