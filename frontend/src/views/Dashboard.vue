<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" :xs="12"><el-card><el-statistic title="关键词总数" :value="stats.total_keywords" /></el-card></el-col>
      <el-col :span="6" :xs="12"><el-card><el-statistic title="已检测" :value="stats.checked_keywords" /></el-card></el-col>
      <el-col :span="6" :xs="12"><el-card><el-statistic title="平均 GEO 得分" :value="stats.avg_geo_score" /></el-card></el-col>
      <el-col :span="6" :xs="12"><el-card><el-statistic title="AI 引用率 %" :value="stats.cite_rate" /></el-card></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="16" :xs="24">
        <el-card header="检测趋势（近7天）">
          <div ref="trendRef" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="8" :xs="24">
        <el-card header="各 AI 平台引用率">
          <el-table :data="stats.engines || []" size="small">
            <el-table-column prop="name" label="平台" />
            <el-table-column prop="checks" label="检测次数" width="90" />
            <el-table-column prop="cite_rate" label="引用率%" width="90" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12" :xs="24">
        <el-card header="最近检测">
          <el-table :data="recent" size="small">
            <el-table-column prop="keyword" label="关键词" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }"><el-tag size="small" :type="row.status === 'SUCCESS' ? 'success' : 'info'">{{ row.status }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="geo_score" label="GEO 分" width="80" />
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12" :xs="24">
        <el-card header="GEO 优化最佳实践">
          <el-table :data="practices" size="small">
            <el-table-column prop="title" label="要点" width="150" />
            <el-table-column prop="detail" label="说明" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const stats = ref({})
const recent = ref([])
const practices = ref([])
const trendRef = ref(null)
let chart = null
const onResize = () => { if (chart) chart.resize() }

function fmt(s) { return (s || '').replace('T', ' ').slice(0, 19) }

onMounted(async () => {
  stats.value = await api.get('/api/keywords/dashboard/')
  recent.value = await api.get('/api/keywords/dashboard/recent/?limit=8')
  practices.value = await api.get('/api/keywords/dashboard/best-practices/?limit=8')
  const trend = await api.get('/api/keywords/dashboard/trend/?range=7days')
  await nextTick()
  chart = echarts.init(trendRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['检测次数', '被引用次数', '平均得分'] },
    grid: { left: 40, right: 40, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: trend.map(t => t.date.slice(5)) },
    yAxis: [{ type: 'value' }, { type: 'value', max: 100 }],
    series: [
      { name: '检测次数', type: 'bar', data: trend.map(t => t.checks) },
      { name: '被引用次数', type: 'bar', data: trend.map(t => t.cited) },
      { name: '平均得分', type: 'line', yAxisIndex: 1, smooth: true, data: trend.map(t => t.avg_score) }
    ]
  })
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>
