<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <el-input v-model="q.search" placeholder="搜索关键词" style="width:220px" clearable @keyup.enter="load" />
        <el-select v-model="q.brand_id" placeholder="全部品牌" style="width:160px" clearable>
          <el-option v-for="b in brands" :key="b.id" :label="b.name" :value="b.id" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button type="success" @click="importVisible = true">批量导入</el-button>
        <el-button :disabled="!selected.length" type="warning" @click="batchCheck">检测选中 ({{ selected.length }})</el-button>
        <el-button :disabled="!selected.length" type="danger" plain @click="batchDelete">删除选中</el-button>
        <el-button style="margin-left:auto" @click="exportCsv">导出 CSV</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" style="margin-top:12px" @selection-change="s => selected = s">
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="keyword" label="关键词" min-width="160" />
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="geo_score" label="GEO 得分" width="110">
          <template #default="{ row }">
            <el-progress :percentage="row.geo_score" :color="scoreColor(row.geo_score)" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="checkOne(row)">检测</el-button>
            <el-button size="small" @click="showReport(row)">报告</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:12px" layout="total, prev, pager, next" :total="total"
                     :page-size="q.page_size" v-model:current-page="q.page" @current-change="load" />
    </el-card>

    <el-dialog v-model="importVisible" title="批量导入关键词" width="520px">
      <el-input v-model="importText" type="textarea" :rows="6" placeholder="每行一个关键词" />
      <el-select v-model="importBrand" placeholder="关联品牌（可选）" style="margin-top:10px;width:100%" clearable>
        <el-option v-for="b in brands" :key="b.id" :label="b.name" :value="b.id" />
      </el-select>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="doImport">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportVisible" title="检测报告" width="760px">
      <div v-if="report.keyword">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="关键词">{{ report.keyword }}</el-descriptions-item>
          <el-descriptions-item label="GEO 综合分">{{ report.geo_score }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ report.status }}</el-descriptions-item>
        </el-descriptions>
        <div v-for="(r, i) in report.results || []" :key="i" style="margin-top:12px">
          <el-tag size="small">{{ r.engine }}</el-tag>
          <el-tag size="small" :type="r.cited ? 'success' : 'danger'" style="margin-left:6px">
            {{ r.cited ? '被引用' : '未引用' }}
          </el-tag>
          <el-tag size="small" style="margin-left:6px">情感：{{ r.sentiment }}</el-tag>
          <el-tag size="small" style="margin-left:6px">得分：{{ r.geo_score }}</el-tag>
          <el-input type="textarea" :rows="4" :model-value="r.answer" readonly style="margin-top:6px" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const rows = ref([]), total = ref(0), loading = ref(false), selected = ref([])
const brands = ref([])
const q = reactive({ page: 1, page_size: 20, search: '', brand_id: null })
const importVisible = ref(false), importText = ref(''), importBrand = ref(null)
const reportVisible = ref(false), report = ref({})

const statusType = s => ({ checked: 'success', checking: 'warning', pending: 'info', failed: 'danger' }[s] || 'info')
const scoreColor = v => (v >= 70 ? '#67C23A' : v >= 40 ? '#E6A23C' : '#F56C6C')

async function load() {
  loading.value = true
  try {
    const d = await api.get('/api/keywords/keyword-library/', { params: { ...q, brand_id: q.brand_id || undefined } })
    rows.value = d.results; total.value = d.count
  } finally { loading.value = false }
}

async function loadBrands() {
  const d = await api.get('/api/account_info/brands/')
  brands.value = d.results || []
}

async function doImport() {
  const list = importText.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!list.length) return ElMessage.warning('请输入关键词')
  const d = await api.post('/api/keywords/bulk-import/', { keywords: list, brand_id: importBrand.value })
  ElMessage.success('导入 ' + d.created + ' 个，跳过 ' + d.skipped + ' 个')
  importVisible.value = false; importText.value = ''
  load()
}

function pollTask(taskId) {
  const timer = setInterval(async () => {
    const d = await api.get('/api/celery_tasks/task-status/' + taskId + '/')
    if (['SUCCESS', 'FAILURE'].includes(d.status)) {
      clearInterval(timer)
      if (d.status === 'SUCCESS') ElMessage.success('检测完成')
      else ElMessage.error('检测失败：' + (d.result && d.result.error || ''))
      load()
    }
  }, 1500)
}

async function checkOne(row) {
  const d = await api.post('/api/keywords/keywords/' + row.id + '/check/', { engines: [] })
  ElMessage.info('已提交检测任务')
  pollTask(d.task_id)
}

async function batchCheck() {
  const d = await api.post('/api/keywords/checks/', { keywords: selected.value.map(r => r.id), engines: [] })
  ElMessage.info('已提交 ' + d.count + ' 个检测任务')
  d.tasks.forEach(t => pollTask(t.task_id))
}

async function batchDelete() {
  await ElMessageBox.confirm('确认删除选中的 ' + selected.value.length + ' 个关键词？', '提示', { type: 'warning' })
  await api.post('/api/keywords/batch-operations/', { action: 'delete', keyword_ids: selected.value.map(r => r.id) })
  ElMessage.success('已删除'); load()
}

async function del(row) {
  await ElMessageBox.confirm('确认删除「' + row.keyword + '」？', '提示', { type: 'warning' })
  await api.delete('/api/keywords/keywords/' + row.id + '/')
  load()
}

async function showReport(row) {
  if (!row.last_check_id) return ElMessage.warning('该关键词还未检测')
  report.value = await api.get('/api/keywords/checks/' + row.last_check_id + '/')
  reportVisible.value = true
}

function exportCsv() { window.open('/api/keywords/export/', '_blank') }

onMounted(() => { load(); loadBrands() })
</script>
