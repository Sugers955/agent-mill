<template>
  <div class="mb-page">
    <header class="mb-header">
      <button class="mb-icon-btn" @click="goBack" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <div class="mb-header-title"><span class="name">个人中心</span></div>
      <div style="width:36px"></div>
    </header>

    <div class="me-body">
      <section class="profile">
        <div class="avatar">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        </div>
        <div class="who">
          <div class="name">{{ auth.user?.display_name || auth.user?.username || '-' }}</div>
          <div class="meta">
            <span class="role">{{ auth.user?.role?.name || '-' }}</span>
            <span v-if="auth.user?.department?.name" class="dept">· {{ auth.user.department.name }}</span>
          </div>
        </div>
      </section>

      <section class="group">
        <div class="group-title">账户</div>
        <div class="group-card">
          <div class="row" @click="changePasswordOpen = true">
            <div class="row-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            <div class="row-text">修改密码</div>
            <span class="arrow">›</span>
          </div>
        </div>
      </section>

      <section class="group">
        <div class="group-title">其他</div>
        <div class="group-card">
          <div class="row" @click="onLogout">
            <div class="row-icon danger">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            </div>
            <div class="row-text danger">退出登录</div>
            <span class="arrow">›</span>
          </div>
        </div>
      </section>
    </div>

    <!-- Change password sheet -->
    <div :class="['mb-drawer-mask', { open: changePasswordOpen }]" @click="closePwd" />
    <div :class="['mb-sheet', { open: changePasswordOpen }]">
      <div class="mb-sheet-handle" />
      <div class="mb-sheet-title">修改密码</div>
      <div class="mb-sheet-body pwd-body">
        <label class="field">
          <span>原密码</span>
          <input v-model="pwd.old" type="password" placeholder="请输入原密码" autocomplete="current-password" />
        </label>
        <label class="field">
          <span>新密码</span>
          <input v-model="pwd.next" type="password" placeholder="不少于 6 位" autocomplete="new-password" />
        </label>
        <label class="field">
          <span>确认新密码</span>
          <input v-model="pwd.confirm" type="password" placeholder="再次输入新密码" autocomplete="new-password" />
        </label>
        <button class="primary-btn" :disabled="pwdLoading" @click="onSubmitPwd">
          {{ pwdLoading ? '提交中…' : '提交' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMobileAuth } from '../stores/auth'
import { useMobileChat } from '../stores/chat'
import { api } from '../api'
import { showToast } from '../toast'

const router = useRouter()
const auth = useMobileAuth()
const chat = useMobileChat()

const changePasswordOpen = ref(false)
const pwdLoading = ref(false)
const pwd = reactive({ old: '', next: '', confirm: '' })

function goBack() {
  if (window.history.length > 1) router.back()
  else router.replace('/chat')
}

function closePwd() {
  changePasswordOpen.value = false
}

async function onSubmitPwd() {
  if (!pwd.old || !pwd.next || !pwd.confirm) {
    showToast('请填写完整')
    return
  }
  if (pwd.next.length < 6) {
    showToast('新密码至少 6 位')
    return
  }
  if (pwd.next !== pwd.confirm) {
    showToast('两次新密码不一致')
    return
  }
  pwdLoading.value = true
  try {
    await api.changePassword(pwd.old, pwd.next)
    showToast('密码已更新，请重新登录', 'success')
    pwd.old = ''; pwd.next = ''; pwd.confirm = ''
    changePasswordOpen.value = false
    auth.logout()
    chat.reset()
    setTimeout(() => router.replace('/login'), 600)
  } catch {
    // toast already shown
  } finally {
    pwdLoading.value = false
  }
}

function onLogout() {
  if (!window.confirm('确定退出登录？')) return
  auth.logout()
  chat.reset()
  router.replace('/login')
}
</script>

<style scoped>
.me-body {
  flex: 1; overflow: auto;
  padding: 14px 12px 24px;
}
.profile {
  display: flex; align-items: center; gap: 14px;
  padding: 18px 16px;
  background: var(--m-surface);
  border-radius: 14px;
  margin-bottom: 18px;
  box-shadow: var(--m-shadow-1);
}
.avatar {
  width: 56px; height: 56px; border-radius: 50%;
  background: var(--m-primary-soft);
  color: var(--m-primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.who { flex: 1; min-width: 0; }
.who .name {
  font-size: 17px; font-weight: 600; color: var(--m-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.who .meta {
  margin-top: 4px;
  font-size: 12px; color: var(--m-text-secondary);
}

.group { margin-bottom: 18px; }
.group-title {
  font-size: 12px; color: var(--m-text-secondary);
  padding: 0 4px 8px; letter-spacing: .03em;
}
.group-card {
  background: var(--m-surface);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: var(--m-shadow-1);
}
.row {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--m-border);
  font-size: 15px;
}
.row:last-child { border-bottom: none; }
.row:active { background: var(--m-surface-variant); }
.row-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--m-primary-soft); color: var(--m-primary);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.row-icon.danger { background: #fce8e6; color: var(--m-danger); }
.row-text { flex: 1; }
.row-text.danger { color: var(--m-danger); }
.arrow { color: var(--m-text-tertiary); font-size: 18px; }

.pwd-body { padding: 12px 16px 24px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 13px; color: var(--m-text-secondary); padding-left: 2px; }
.field input {
  height: 44px; padding: 0 14px;
  border: 1px solid var(--m-border); border-radius: 10px;
  background: #fff; font-size: 15px; outline: none;
}
.field input:focus { border-color: var(--m-primary); box-shadow: 0 0 0 3px var(--m-primary-soft); }

.primary-btn {
  height: 46px; margin-top: 6px;
  background: var(--m-primary); color: #fff;
  border-radius: 12px; font-size: 15px; font-weight: 500;
  display: flex; align-items: center; justify-content: center;
}
.primary-btn:active { background: var(--m-primary-hover); }
.primary-btn:disabled { background: var(--m-border-strong); }
</style>
