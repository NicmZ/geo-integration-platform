<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <el-select v-model="status" placeholder="全部状态" style="width:150px" clearable>
          <el-option v-for="s in ['pending', 'publishing', 'success', 'failed', 'cancelled']" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button @click="load">刷新</el-button>
        <el-tag type="info" style="margin-left:auto">插件状态：{{ extStatus.online ? '在线' : '离线' }}</el-tag>
      </div>

      <el-table :data="rows" v-loading="loading" style="margin-top:12px" size="small">
        <el-table-column prop="id" label="任务ID" width="300" show-overflow-tooltip />
        <el-table-column prop="content_id" label="内容ID" width="80" />
        <el-table-column prop="platform_key" label="平台" width="120" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="{ success: 'success', failed: 'danger', publishing: 'warning' }[row.status] || 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cost" label="费用¥" width="80" />
        <el-table-column prop="publish_url" label="发布链接" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <a v-if="row.publish_url" :href="row.publish_url" target="_blank">{{ row.publish_url }}</a>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="['pending', 'failed'].includes(row.status)" size="small" @click="retry(row)">重试</el-button>
            <el-button v-if="['pending', 'publishing'].includes(row.status)" size="small" type="warning" plain @click="cancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card header="媒体库渠道（媒体采购）" style="margin-top:16px">
      <div style="display:flex;gap:10px;margin-bottom:10px">
        <el-select v-model="mq.channel" placeholder="类别" style="width:120px" clearable @change="loadMedia">
          <el-option label="综合门户" value="C" /><el-option label="垂直媒体" value="V" />
          <el-option label="新媒体" value="X" /><el-option label="微信生态" value="W" />
        </el-select>
        <el-input v-model="mq.search" placeholder="搜索渠道" style="width:200px" clearable @keyup.enter="loadMedia" />
        <el-button @click="loadMedia">查询</el-button>
      </div>
      <el-table :data="media.items" size="small" v-loading="mediaLoading">
        <el-table-column prop="channel_name" label="渠道名称" min-width="180" />
        <el-table-column prop="platform_key" label="平台" width="110" />
        <el-table-column prop="category" label="类别" width="70" />
        <el-table-column prop="followers" label="粉丝数" width="100" />
        <el-table-column prop="price" label="刊例价¥" width="100" />
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>
      <el-pagination style="margin-top:10px" layout="total, prev, pager, next" :total="media.total"
                     :page-size="mq.page_size" v-model:current-page="mq.page" @current-change="loadMedia" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const rows = ref([]), loading = ref(false), status = ref(''), extStatus = ref({})
const media = ref({ items: [], total: 0 }), mediaLoading = ref(false)
const mq = reactive({ channel: '', search: '', page: 1, page_size: 10 })

async function load() {
  loading.value = true
  try {
    const d = await api.get('/api/content/publish-tasks/', { params: { page: 1, page_size: 50, status: status.value || undefined } })
    rows.value = d.results
    extStatus.value = await api.get('/api/extension_monitor/publisher-status/')
  } finally { loading.value = false }
}

async function loadMedia() {
  mediaLoading.value = true
  try {
    media.value = await api.get('/api/media_db/media/', { params: { ...mq } })
  } finally { mediaLoading.value = false }
}

async function retry(row) {
  await api.post('/api/content/publish-tasks/' + row.id + '/retry/')
  ElMessage.success('已重新提交'); load()
}

async function cancel(row) {
  await api.post('/api/content/publish-tasks/' + row.id + '/cancel/')
  ElMessage.success('已取消'); load()
}

onMounted(() => { load(); loadMedia() })
</script>
