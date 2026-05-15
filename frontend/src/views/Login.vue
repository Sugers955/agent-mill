<template>
  <div class="login-bg">
    <div class="login-shape shape-1" />
    <div class="login-shape shape-2" />
    <div class="login-shape shape-3" />
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">
          <span class="dot dot-1" /><span class="dot dot-2" /><span class="dot dot-3" /><span class="dot dot-4" />
        </div>
        <div class="brand-name">Agent Forge</div>
      </div>
      <h2 class="title">欢迎回来</h2>
      <p class="subtitle">登录后开始与你的智能体协作</p>

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
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const STORAGE_KEY = 'remembered_login'

const auth = useAuth()
const router = useRouter()
const formRef = ref<any>(null)
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const rememberMe = ref(false)
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const { username, password } = JSON.parse(saved)
      form.username = username || ''
      form.password = password || ''
      rememberMe.value = true
    }
  } catch { localStorage.removeItem(STORAGE_KEY) }
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
    router.push('/chat')
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-bg {
  position: relative;
  display: flex; align-items: center; justify-content: center;
  height: 100vh; overflow: hidden;
  background: linear-gradient(135deg, #fafbfc 0%, #f1f3f4 100%);
}
.login-shape {
  position: absolute; border-radius: 50%; filter: blur(80px); opacity: .55;
}
.shape-1 { width: 420px; height: 420px; background: #4285f4; top: -120px; left: -120px; }
.shape-2 { width: 380px; height: 380px; background: #34a853; bottom: -100px; right: -80px; }
.shape-3 { width: 280px; height: 280px; background: #fbbc04; top: 40%; right: 30%; opacity: .35; }

.login-card {
  position: relative; z-index: 1;
  width: 420px; padding: 40px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(20px) saturate(160%);
  border-radius: 28px;
  border: 1px solid rgba(255,255,255,.6);
  box-shadow: 0 20px 60px rgba(60,64,67,.18);
}
.brand { display:flex; align-items:center; gap: 10px; margin-bottom: 28px; }
.brand-mark { display:grid; grid-template-columns: 1fr 1fr; gap: 3px; width: 22px; height: 22px; }
.dot { border-radius: 50%; }
.dot-1 { background:#4285f4 } .dot-2 { background:#ea4335 }
.dot-3 { background:#fbbc04 } .dot-4 { background:#34a853 }
.brand-name { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }

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
</style>
