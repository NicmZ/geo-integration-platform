<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8" :xs="24">
        <el-card>
          <el-statistic title="当前余额（元）" :value="balance" />
          <el-button type="primary" style="margin-top:12px;width:100%" @click="rechargeVisible = true">充值</el-button>
        </el-card>
      </el-col>
      <el-col :span="16" :xs="24">
        <el-card header="套餐">
          <el-table :data="plans" size="small">
            <el-table-column prop="name" label="套餐" />
            <el-table-column prop="amount" label="价格¥" width="90" />
            <el-table-column prop="credits" label="到账¥" width="90" />
            <el-table-column label="操作" width="110">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="buy(row)">购买</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card header="消费/充值流水" style="margin-top:16px">
      <el-table :data="records" v-loading="loading" size="small">
        <el-table-column prop="record_id" label="流水号" width="120" />
        <el-table-column prop="record_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="{ consume: 'warning', recharge: 'success', gift: 'success', refund: 'info' }[row.record_type]">
              {{ { consume: '消费', recharge: '充值', gift: '赠送', refund: '退款' }[row.record_type] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额¥" width="90" />
        <el-table-column prop="balance_after" label="余额¥" width="90" />
        <el-table-column prop="description" label="说明" min-width="200" />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:12px" layout="total, prev, pager, next" :total="total"
                     :page-size="q.page_size" v-model:current-page="q.page" @current-change="loadRecords" />
    </el-card>

    <el-dialog v-model="rechargeVisible" title="充值" width="420px">
      <el-form label-width="90px">
        <el-form-item label="套餐">
          <el-select v-model="planType" style="width:100%">
            <el-option v-for="p in plans" :key="p.plan_type" :label="p.name + ' ¥' + p.amount" :value="p.plan_type" />
          </el-select>
        </el-form-item>
        <el-form-item label="支付方式">
          <el-radio-group v-model="payMethod">
            <el-radio value="alipay">支付宝</el-radio>
            <el-radio value="wechat">微信</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rechargeVisible = false">取消</el-button>
        <el-button type="primary" @click="doRecharge">确认支付</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const balance = ref(0), records = ref([]), total = ref(0), loading = ref(false)
const plans = ref([]), rechargeVisible = ref(false), planType = ref('credits_50'), payMethod = ref('alipay')
const q = reactive({ page: 1, page_size: 20 })

async function load() {
  const d = await api.get('/api/account_info/balance')
  balance.value = d.balance
  loadRecords()
  plans.value = await api.get('/api/payment/plans/')
}

async function loadRecords() {
  loading.value = true
  try {
    const d = await api.get('/api/account_info/consumption-records/', { params: q })
    records.value = d.results; total.value = d.count
  } finally { loading.value = false }
}

async function buy(plan) {
  planType.value = plan.plan_type
  rechargeVisible.value = true
}

async function doRecharge() {
  const d = await api.post('/api/payment/create/', { plan_type: planType.value, payment_method: payMethod.value })
  ElMessage.success('支付成功（沙箱），到账 ¥' + (d.balance_after ?? ''))
  rechargeVisible.value = false
  load()
}

onMounted(load)
</script>
