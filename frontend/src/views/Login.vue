<template>
  <div class="login-bg">
    <div class="login-shape shape-1" />
    <div class="login-shape shape-2" />
    <div class="login-shape shape-3" />
    <div class="login-card">
      <div class="brand">
        <img class="brand-logo" src="/logo-icon.png" alt="Agent Mill" />
        <div class="brand-text">
          <div class="brand-name">Agent Mill</div>
          <div class="brand-slogan">你的数字员工工厂</div>
        </div>
      </div>
      <h2 class="title">欢迎回来</h2>
      <p class="subtitle">让 AI 员工为你工作</p>

      <el-form @submit.prevent="onSubmit" :model="form" :rules="rules" ref="formRef" label-position="top" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autofocus placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="输入密码" />
        </el-form-item>
        <div class="remember-row">
          <label class="remember-label">
            <input type="checkbox" v-model="rememberMe" class="remember-check" />
            记住密码
          </label>
        </div>
        <el-button type="primary" :loading="loading" style="width:100%;height:44px;font-size:15px" @click="onSubmit">
          登录
        </el-button>
        <div v-if="ssoEnabled" class="sso-divider"><span>或</span></div>
        <el-button v-if="ssoEnabled" class="sso-btn" @click="onSSOLogin">
          <svg class="sso-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9-4-18-3 9H2"/></svg>
          企业 SSO 登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'
import { api } from '@/api'

const STORAGE_KEY = 'remembered_login'

const auth = useAuth()
const router = useRouter()
const formRef = ref<any>(null)
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const rememberMe = ref(false)
const ssoEnabled = ref(false)
const ssoConfig = ref<any>(null)
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(async () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const { username, password } = JSON.parse(saved)
      form.username = username || ''
      form.password = password || ''
      rememberMe.value = true
    }
  } catch { localStorage.removeItem(STORAGE_KEY) }
  
  // 检查 SSO 配置
  try {
    const res = await api.ssoConfig()
    ssoEnabled.value = res.enabled
    ssoConfig.value = res.config
  } catch {}
})

async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    if (rememberMe.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ username: form.username, password: form.password }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
    router.push('/chat').catch(() => {})
  } finally { loading.value = false }
}

function onSSOLogin() {
  if (!ssoConfig.value) return
  const { issuer_url, client_id, redirect_uri } = ssoConfig.value
  if (!issuer_url || !client_id || !redirect_uri) return
  const authUrl = `${issuer_url}/authorize?response_type=code&client_id=${client_id}&redirect_uri=${encodeURIComponent(redirect_uri)}&scope=openid%20profile%20email`
  window.location.href = authUrl
}
</script>

<style scoped>
.login-bg {
  position: relative;
  display: flex; align-items: center; justify-content: center;
  height: 100vh; overflow: hidden;
  background: linear-gradient(135deg, var(--m-surface) 0%, var(--m-bg-soft) 100%);
}
.login-shape {
  position: absolute; border-radius: 50%; filter: blur(80px); opacity: .55;
}
.shape-1 { width: 420px; height: 420px; background: var(--m-primary); top: -120px; left: -120px; }
.shape-2 { width: 380px; height: 380px; background: var(--m-success); bottom: -100px; right: -80px; }
.shape-3 { width: 280px; height: 280px; background: var(--m-warning); top: 40%; right: 30%; opacity: .35; }

.login-card {
  position: relative; z-index: 1;
  width: 420px; padding: 40px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(20px) saturate(160%);
  border-radius: 28px;
  border: 1px solid rgba(255,255,255,.6);
  box-shadow: 0 20px 60px rgba(60,64,67,.18);
}
.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 32px;
}
.brand-logo {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  object-fit: contain;
  flex-shrink: 0;
  box-shadow: 0 4px 16px rgba(0,0,0,.1);
  background: var(--m-surface);
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.brand-name {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--m-text);
}
.brand-slogan {
  font-size: 13px;
  color: var(--m-text-tertiary);
  letter-spacing: 0.02em;
}

.title { margin: 0 0 4px; font-size: 28px; font-weight: 600; letter-spacing: -0.02em; }
.subtitle { margin: 0 0 24px; color: var(--m-text-secondary); font-size: 14px; }

.footer-hint { margin-top: 20px; text-align: center; color: var(--m-text-tertiary); font-size: 12px; }
.footer-hint code { background: var(--m-surface-variant); padding: 2px 6px; border-radius: 4px; }

.remember-row { margin: -4px 0 14px; }
.remember-label {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--m-text-secondary);
  cursor: pointer; user-select: none;
}
.remember-check { width: 14px; height: 14px; accent-color: var(--m-primary); cursor: pointer; }
.sso-divider {
  display: flex; align-items: center; gap: 12px; margin: 16px 0; color: var(--m-text-tertiary); font-size: 13px;
}
.sso-divider::before, .sso-divider::after {
  content: ''; flex: 1; height: 1px; background: var(--m-border);
}
.sso-btn {
  width: 100%; height: 40px; font-size: 14px;
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--m-border);
  --el-button-hover-bg-color: var(--m-surface-variant);
}
.sso-icon { width: 16px; height: 16px; margin-right: 4px; }
</style>
