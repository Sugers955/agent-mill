import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElIcons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles.css'

const savedTheme = localStorage.getItem('theme')
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
document.documentElement.setAttribute('data-theme', savedTheme || (prefersDark ? 'dark' : 'light'))

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
for (const [k, v] of Object.entries(ElIcons)) app.component(k, v as any)
app.mount('#app')
