<template>
  <div>
    <el-card>
      <div style="display:flex;gap:10px;align-items:center">
        <el-button type="primary" @click="createVisible = true">新建工单</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" style="margin-top:12px" size="small">
        <el-table-column prop="ticket_no" label="工单号" width="150" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="{ open: 'info', processing: 'warning', responded: 'success', closed: '' }[row.status]">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="view(row)">详情</el-button>
            <el-button v-if="row.status !== 'closed'" size="small" type="warning" plain @click="close(row)">关闭</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建工单" width="520px">
      <el-form label-width="70px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width:100%">
            <el-option v-for="c in ['功能异常', '计费问题', '产品建议', '数据问题', '其他']" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="create">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="viewVisible" :title="current.title" width="640px">
      <p>{{ current.content }}</p>
      <el-divider>回复</el-divider>
      <div v-for="r in responses" :key="r.id" style="margin-bottom:10px">
        <el-tag size="small">{{ r.responder_type }}</el-tag>
        <span style="margin-left:8px">{{ r.content }}</span>
      </div>
      <el-input v-model="reply" type="textarea" :rows="2" placeholder="补充说明…" style="margin-top:8px" />
      <template #footer>
        <el-button @click="viewVisible = false">关闭</el-button>
        <el-button type="primary" @click="respond">回复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const rows = ref([]), loading = ref(false), createVisible = ref(false)
const form = ref({ title: '', category: '其他', content: '' })
const viewVisible = ref(false), current = ref({}), responses = ref([]), reply = ref('')

async function load() {
  loading.value = true
  try { rows.value = await api.get('/api/feedback/my-feedbacks/') } finally { loading.value = false }
}

async function create() {
  await api.post('/api/feedback/feedbacks/', form.value)
  ElMessage.success('工单已提交')
  createVisible.value = false
  form.value = { title: '', category: '其他', content: '' }
  load()
}

async function view(row) {
  const d = await api.get('/api/feedback/feedbacks/' + row.id + '/')
  current.value = d; responses.value = d.responses || []
  viewVisible.value = true
}

async function respond() {
  if (!reply.value) return
  await api.post('/api/feedback/feedbacks/' + current.value.id + '/respond/', { content: reply.value })
  reply.value = ''
  view(current.value)
}

async function close(row) {
  await ElMessageBox.confirm('确认关闭该工单？', '提示', { type: 'warning' })
  await api.post('/api/feedback/feedbacks/' + row.id + '/close/')
  load()
}

onMounted(load)
</script>
