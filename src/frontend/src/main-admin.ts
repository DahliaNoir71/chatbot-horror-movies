import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router/admin'
import { useAuthStore, setStoragePrefix } from '@/stores/auth.store'
import { setLoginUrl } from '@/api/auth-redirect'
import { setTokenKey } from '@/api/client'
import './style.css'
import AppAdmin from './AppAdmin.vue'

const app = createApp(AppAdmin)
app.use(createPinia())

setStoragePrefix('horrorbot_admin')
setTokenKey('horrorbot_admin_token')

const authStore = useAuthStore()
authStore.initFromStorage()
setLoginUrl('/admin.html#/login')

app.use(router)
app.mount('#app')
