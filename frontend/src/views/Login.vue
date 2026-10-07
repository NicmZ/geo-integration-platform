<template>
  <div class="login-bg">
    <el-card class="login-card">
      <h2 class="tt">GEO 一站式优化平台</h2>
      <p class="sub">AI 搜索优化 · 合规检测 · 内容生产 · 全渠道发布</p>
      <el-form @keyup.enter="doLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password />
        </el-form-item>
        <el-form-item v-if="captchaEnabled">
          <div style="display:flex;gap:8px;width:100%">
            <el-input v-model="form.captcha_code" placeholder="验证码" size="large" />
            <img v-if="captchaImg" :src="captchaImg" class="captcha" @click="loadCaptcha" title="点击刷新" />
          </div>
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="doLogin">登 录</el-button>
        <div style="text-align:center;margin-top:10px">
          <el-button link type="primary" @click="doRegister">没有账号？立即注册</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const form = ref({ username: '', password: '', captcha_code: '' })
const captchaImg = ref('')
const captchaToken = ref('')
const captchaEnabled = ref(false)
const loading = ref(false)

async function loadCaptcha() {
  const d = await api.get('/api/users/captcha/')
  captchaImg.value = d.captcha_image
  captchaToken.value = d.captcha_token
}

async function submit(path, extra = {}) {
  loading.value = true
  try {
    const d = await api.post(path, {
      username: form.value.username, password: form.value.password,
      captcha_token: captchaToken.value, captcha_code: form.value.captcha_code, ...extra
    })
    localStorage.setItem('geo_token', d.token)
    localStorage.setItem('geo_profile', JSON.stringify(d.user))
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}

function doLogin() {
  if (!form.value.username || !form.value.password) return ElMessage.warning('请输入用户名和密码')
  submit('/api/users/login/')
}

function doRegister() {
  if (!form.value.username || form.value.username.length < 3) return ElMessage.warning('用户名至少 3 位')
  if (!form.value.password || form.value.password.length < 6) return ElMessage.warning('密码至少 6 位')
  submit('/api/users/register/')
}

onMounted(async () => {
  try {
    await loadCaptcha()
    captchaEnabled.value = true
  } catch (e) { captchaEnabled.value = false }
})
</script>

<style scoped>
.login-bg { height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1d2535 0%, #2b4a6f 60%, #409EFF 130%); }
.login-card { width: 400px; padding: 12px 8px; }
.tt { text-align: center; margin: 8px 0 4px; color: #1d2535; }
.sub { text-align: center; color: #909399; font-size: 12px; margin-bottom: 24px; }
.captcha { height: 40px; border-radius: 4px; cursor: pointer; }
@media (max-width: 480px) {
  .login-card { width: 92% !important; max-width: 400px; }
  .login-bg { padding: 0 12px; box-sizing: border-box; }
  .tt { font-size: 20px; }
}
</style>
