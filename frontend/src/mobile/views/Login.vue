<template>
  <div class="login-wrap">
    <div class="hero">
      <div class="brand-row">
        <img class="brand-logo" src="/logo-main.png" alt="Agent Mill" />
      </div>
      <div class="welcome">欢迎回来</div>
      <div class="subtitle">让 AI 员工为你工作</div>
    </div>

    <form class="form" @submit.prevent="onSubmit">
      <label class="field">
        <span>用户名</span>
        <input v-model="form.username" type="text" placeholder="输入用户名" autocomplete="username" />
      </label>
      <label class="field">
        <span>密码</span>
        <input v-model="form.password" type="password" placeholder="输入密码" autocomplete="current-password" />
      </label>
      <label class="remember-label">
        <input type="checkbox" v-model="rememberMe" class="remember-check" />
        记住密码
      </label>
      <button class="primary-btn" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMobileAuth } from '../stores/auth'
import { showToast } from '../toast'

const STORAGE_KEY = 'remembered_login'

const router = useRouter()
const auth = useMobileAuth()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const rememberMe = ref(false)

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
  if (!form.username.trim() || !form.password) {
    showToast('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    if (rememberMe.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ username: form.username.trim(), password: form.password }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
    router.replace('/chat')
  } catch {
    // toast already shown
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100%;
  background: linear-gradient(160deg, #eaf1ff 0%, #f5f7fb 60%, #fff 100%);
  display: flex; flex-direction: column;
  padding: 0 24px;
  padding-top: calc(env(safe-area-inset-top, 16px) + 60px);
  padding-bottom: calc(var(--safe-bottom) + 24px);
}
.hero { text-align: center; margin-bottom: 36px; }
.brand-row { display: flex; align-items: center; justify-content: center; margin-bottom: 24px; }
.brand-logo {
  width: 160px;
  height: auto;
  object-fit: contain;
}
.welcome { font-size: 26px; font-weight: 600; letter-spacing: -.01em; }
.subtitle { color: var(--m-text-secondary); font-size: 14px; margin-top: 6px; }

.form { display: flex; flex-direction: column; gap: 14px; }
.field {
  display: flex; flex-direction: column; gap: 6px;
}
.field span { font-size: 13px; color: var(--m-text-secondary); padding-left: 2px; }
.field input {
  height: 48px;
  padding: 0 14px;
  border: 1px solid var(--m-border);
  border-radius: 12px;
  background: #fff;
  font-size: 15px;
  outline: none;
  transition: border-color .15s, box-shadow .15s;
}
.field input:focus {
  border-color: var(--m-primary);
  box-shadow: 0 0 0 3px var(--m-primary-soft);
}

.primary-btn {
  margin-top: 12px;
  height: 48px;
  background: var(--m-primary);
  color: #fff;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 500;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.primary-btn:active { background: var(--m-primary-hover); }
.primary-btn:disabled { background: var(--m-border-strong); }

.remember-label {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 14px; color: var(--m-text-secondary);
  cursor: pointer; user-select: none;
  margin-top: -4px;
}
.remember-check { width: 16px; height: 16px; accent-color: var(--m-primary); cursor: pointer; }
</style>
