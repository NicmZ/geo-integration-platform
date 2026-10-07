<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <el-button type="primary" @click="openGenerate">AI 生成内容</el-button>
        <el-input v-model="q.search" placeholder="搜索标题" style="width:220px" clearable @keyup.enter="load" />
        <el-button @click="load">刷新</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" style="margin-top:12px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="{ ready: 'success', generating: 'warning', draft: 'info', failed: 'danger' }[row.status]">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="engine_key" label="生成引擎" width="110" />
        <el-table-column prop="cost" label="费用¥" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <el-button size="small" @click="view(row)">查看</el-button>
            <el-button size="small" type="success" @click="openPublish(row)">发布</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:12px" layout="total, prev, pager, next" :total="total"
                     :page-size="q.page_size" v-model:current-page="q.page" @current-change="load" />
    </el-card>

    <el-dialog v-model="genVisible" title="AI 内容生成（GEO 友好）" width="640px">
      <el-form label-width="90px">
        <el-form-item label="标题"><el-input v-model="gen.title" /></el-form-item>
        <el-form-item label="关键词"><el-input v-model="gen.keywords" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="品牌">
          <el-select v-model="gen.brand_id" style="width:100%" clearable>
            <el-option v-for="b in brands" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="生成引擎">
          <el-select v-model="gen.engine_platform_key" style="width:100%">
            <el-option v-for="e in engines" :key="e.key" :label="e.name + ' (' + e.key + ')'" :value="e.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="字数">
          <el-select v-model="gen.length" style="width:100%">
            <el-option :value="600" label="600 字" /><el-option :value="1200" label="1200 字" />
            <el-option :value="2000" label="2000 字" />
          </el-select>
        </el-form-item>
        <el-form-item label="摘要"><el-input v-model="gen.summary" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="特殊要求"><el-input v-model="gen.special_requirements" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="viewVisible" :title="current.title" width="720px">
      <el-input type="textarea" :rows="18" :model-value="current.body" readonly />
    </el-dialog>

    <el-dialog v-model="pubVisible" title="选择发布平台" width="480px">
      <el-checkbox-group v-model="pubPlatforms">
        <el-checkbox v-for="p in platforms" :key="p.key" :value="p.key" style="width:140px">
          {{ p.name }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="pubVisible = false">取消</el-button>
        <el-button type="primary" @click="doPublish">发布（每个平台计费）</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const rows = ref([]), total = ref(0), loading = ref(false), q = reactive({ page: 1, page_size: 20, search: '' })
const brands = ref([]), engines = ref([]), platforms = ref([])
const genVisible = ref(false), genLoading = ref(false)
const gen = reactive({ title: '', keywords: '', brand_id: null, engine_platform_key: 'deepseek', length: 1200, summary: '', special_requirements: '' })
const viewVisible = ref(false), current = ref({})
const pubVisible = ref(false), pubPlatforms = ref([]), pubContentId = ref(null)

async function load() {
  loading.value = true
  try {
    const d = await api.get('/api/content/content/', { params: q })
    rows.value = d.results; total.value = d.count
  } finally { loading.value = false }
}

async function openGenerate() {
  genVisible.value = true
  if (!engines.value.length) {
    engines.value = await api.get('/api/result/engines/choices/')
  }
}

async function doGenerate() {
  if (!gen.title) return ElMessage.warning('请输入标题')
  genLoading.value = true
  try {
    const d = await api.post('/api/content/content/generate-content/', {
      title: gen.title,
      keywords: gen.keywords.split(/[,，]/).map(s => s.trim()).filter(Boolean),
      brand: gen.brand_id ? [gen.brand_id] : [],
      length: gen.length, summary: gen.summary, special_requirements: gen.special_requirements,
      engine_platform_key: gen.engine_platform_key
    })
    ElMessage.success('生成任务已提交')
    genVisible.value = false
    pollTask(d.task_id)
  } finally { genLoading.value = false }
}

function pollTask(taskId) {
  const timer = setInterval(async () => {
    const d = await api.get('/api/celery_tasks/task-status/' + taskId + '/')
    if (['SUCCESS', 'FAILURE'].includes(d.status)) {
      clearInterval(timer)
      if (d.status === 'SUCCESS') ElMessage.success('内容生成完成')
      load()
    }
  }, 1500)
}

async function view(row) {
  const d = await api.get('/api/content/content/' + row.id + '/')
  current.value = d; viewVisible.value = true
}

async function openPublish(row) {
  pubContentId.value = row.id
  if (!platforms.value.length) platforms.value = await api.get('/api/content/media-platforms/')
  pubPlatforms.value = []
  pubVisible.value = true
}

async function doPublish() {
  if (!pubPlatforms.value.length) return ElMessage.warning('请选择平台')
  const d = await api.post('/api/content/publish-tasks/bulk-publish/', {
    content_ids: [pubContentId.value], platforms: pubPlatforms.value
  })
  ElMessage.success('已提交 ' + d.count + ' 个发布任务，合计 ¥' + d.total_cost)
  pubVisible.value = false
}

async function del(row) {
  await ElMessageBox.confirm('确认删除该内容？', '提示', { type: 'warning' })
  await api.delete('/api/content/content/' + row.id + '/')
  load()
}

onMounted(async () => { load(); api.get('/api/account_info/brands/').then(d => brands.value = d.results || []).catch(() => {}) })
</script>
