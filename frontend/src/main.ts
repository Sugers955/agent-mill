import { createApp } from 'vue'
import { createPinia } from 'pinia'
import * as ElIcons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import { initActivityTracker } from './lib/activity'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-loading.css'
import 'element-plus/theme-chalk/el-dialog.css'
import 'element-plus/theme-chalk/el-drawer.css'
import 'element-plus/theme-chalk/el-notification.css'
import './styles.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
for (const [k, v] of Object.entries(ElIcons)) app.component(k, v as any)
initActivityTracker()
app.mount('#app')
