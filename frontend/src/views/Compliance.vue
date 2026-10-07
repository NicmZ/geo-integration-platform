<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <el-select v-model="kwId" placeholder="选择要检测的关键词" style="width:260px" filterable clearable>
          <el-option v-for="k in keywords" :key="k.id" :label="k.keyword" :value="k.id" />
        </el-select>
        <el-button type="primary" :disabled="!kwId" @click="runCheck">发起合规检测</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </el-card>

    <el-card header="合规报告列表" style="margin-top:16px">
      <el-table :data="reports" v-loading="loading" size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="90">
          <template #default="{ row }"><b :style="{ color: scoreColor(row.score) }">{{ row.score }}</b></template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.risk_level === 'high' ? 'danger' : row.risk_level === 'medium' ? 'warning' : 'success'">
              {{ { low: '低', medium: '中', high: '高' }[row.risk_level] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="240" show-overflow-tooltip />
        <el-table-column prop="locked" label="详情" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.locked ? 'warning' : 'success'">{{ row.locked ? '已锁定' : '已解锁' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="row.locked" size="small" type="warning" @click="unlock(row)">付费解锁</el-button>
            <el-button v-else size="small" @click="view(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="合规详情" width="680px">
      <el-table :data="findings" size="small">
        <el-table-column prop="category" label="类别" width="100" />
        <el-table-column prop="severity" label="严重度" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fragment" label="风险片段" min-width="200" show-overflow-tooltip />
        <el-table-column prop="suggestion" label="修改建议" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const keywords = ref([]), reports = ref([]), loading = ref(false)
const kwId = ref(null), detailVisible = ref(false), findings = ref([])

const scoreColor = v => (v >= 85 ? '#67C23A' : v >= 60 ? '#E6A23C' : '#F56C6C')

async function load() {
  loading.value = true
  try {
    const d = await api.get('/api/keywords/keyword-library/', { params: { page: 1, page_size: 100 } })
    keywords.value = d.results
    reports.value = await api.get('/api/keywords/compliance/')
  } finally { loading.value = false }
}

async function runCheck() {
  const d = await api.post('/api/keywords/compliance/', { keyword_id: kwId.value })
  ElMessage.info('合规检测已提交')
  const timer = setInterval(async () => {
    const s = await api.get('/api/celery_tasks/task-status/' + d.task_id + '/')
    if (['SUCCESS', 'FAILURE'].includes(s.status)) {
      clearInterval(timer)
      if (s.status === 'SUCCESS') ElMessage.success('检测完成')
      load()
    }
  }, 1500)
}

async function unlock(row) {
  const d = await api.post('/api/keywords/unlock/', { report_id: row.id })
  ElMessage.success('已解锁，扣费 ¥' + d.cost)
  findings.value = d.findings
  detailVisible.value = true
  load()
}

async function view(row) {
  const d = await api.get('/api/keywords/compliance/' + row.id + '/')
  findings.value = d.findings || []
  detailVisible.value = true
}

onMounted(load)
</script>
