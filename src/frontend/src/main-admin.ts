import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router/admin'
import { useAuthStore } from '@/stores/auth.store'
import { setLoginUrl } from '@/api/auth-redirect'
import './style.css'
import AppAdmin from './AppAdmin.vue'

const app = createApp(AppAdmin)
app.use(createPinia())

const authStore = useAuthStore()
authStore.initFromStorage()
setLoginUrl('/admin.html#/login')

app.use(router)
app.mount('#app')
