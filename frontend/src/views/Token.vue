<template>
  <div>
    <el-card header="GEO 平台接入码（sk-）">
      <el-alert type="info" :closable="false" show-icon
                title="接入码用于调用本平台开放 API（/api/keywords、/api/content 等），也可对接浏览器插件与第三方系统。" />
      <div style="display:flex;gap:12px;align-items:center;margin-top:20px">
        <el-input :model-value="token" readonly style="max-width:480px" />
        <el-button type="primary" @click="reset">重置接入码</el-button>
        <el-button @click="copy">复制</el-button>
      </div>
      <el-alert v-if="resetted" type="warning" :closable="false" show-icon style="margin-top:16px"
                title="接入码已重置，旧接入码立即失效，请更新到所有调用方。" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const token = ref(''), resetted = ref(false)

async function load() {
  const d = await api.get('/api/users/my-token/')
  token.value = d.token
}

async function reset() {
  await ElMessageBox.confirm('重置后旧接入码立即失效，确认继续？', '提示', { type: 'warning' })
  const d = await api.post('/api/users/my-token/', {})
  token.value = d.token
  resetted.value = true
}

async function copy() {
  await navigator.clipboard.writeText(token.value)
  ElMessage.success('已复制')
}

onMounted(load)
</script>
