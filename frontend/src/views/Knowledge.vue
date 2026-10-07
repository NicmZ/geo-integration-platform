<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;align-items:center">
        <el-select v-model="brandId" placeholder="选择品牌" style="width:220px">
          <el-option v-for="b in brands" :key="b.id" :label="b.name" :value="b.id" />
        </el-select>
        <el-button type="primary" :disabled="!brandId" :loading="building" @click="buildKb">构建/更新知识库（¥10）</el-button>
        <el-button @click="loadBrands">刷新品牌</el-button>
      </div>
    </el-card>

    <el-card header="品牌知识库" style="margin-top:16px">
      <el-table :data="kbs" v-loading="loading" size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="brand_id" label="品牌ID" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'published' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">{{ (row.updated_at || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="view(row)">查看</el-button>
            <el-button v-if="row.status !== 'published'" size="small" type="success" @click="publish(row)">发布</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="viewVisible" :title="current.title" width="720px">
      <el-input type="textarea" :rows="18" :model-value="current.content" readonly />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const brands = ref([]), brandId = ref(null), kbs = ref([]), loading = ref(false)
const building = ref(false), viewVisible = ref(false), current = ref({})

async function loadBrands() {
  const d = await api.get('/api/account_info/brands/')
  brands.value = d.results || []
}

async function load() {
  loading.value = true
  try {
    const d = await api.get('/api/account_info/knowledge-base/')
    kbs.value = d.results || []
  } finally { loading.value = false }
}

async function buildKb() {
  building.value = true
  try {
    const d = await api.post('/api/account_info/knowledge-base/create-task/', { brand: brandId.value })
    const timer = setInterval(async () => {
      const s = await api.get('/api/celery_tasks/task-status/' + d.task_id + '/')
      if (['SUCCESS', 'FAILURE'].includes(s.status)) {
        clearInterval(timer); building.value = false
        if (s.status === 'SUCCESS') { ElMessage.success('知识库构建完成'); load() }
        else ElMessage.error('构建失败')
      }
    }, 1500)
  } catch (e) { building.value = false }
}

async function view(row) {
  const d = await api.get('/api/account_info/knowledge-base/' + row.id + '/')
  current.value = d; viewVisible.value = true
}

async function publish(row) {
  await api.put('/api/account_info/knowledge-base/' + row.id + '/publish/')
  ElMessage.success('已发布'); load()
}

async function del(row) {
  await ElMessageBox.confirm('确认删除该知识库？', '提示', { type: 'warning' })
  await api.delete('/api/account_info/knowledge-base/' + row.id + '/')
  load()
}

onMounted(() => { loadBrands(); load() })
</script>
