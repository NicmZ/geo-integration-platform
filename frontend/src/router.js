import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('./views/Login.vue') },
  {
    path: '/',
    component: () => import('./layout/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '数据看板', icon: 'Odometer' } },
      { path: 'keywords', name: 'Keywords', component: () => import('./views/Keywords.vue'), meta: { title: '关键词中心', icon: 'Search' } },
      { path: 'compliance', name: 'Compliance', component: () => import('./views/Compliance.vue'), meta: { title: '合规检测', icon: 'Lock' } },
      { path: 'content', name: 'Content', component: () => import('./views/Content.vue'), meta: { title: 'AI 内容中心', icon: 'EditPen' } },
      { path: 'knowledge', name: 'Knowledge', component: () => import('./views/Knowledge.vue'), meta: { title: '品牌知识库', icon: 'Collection' } },
      { path: 'publish', name: 'Publish', component: () => import('./views/Publish.vue'), meta: { title: '全渠道发布', icon: 'Promotion' } },
      { path: 'billing', name: 'Billing', component: () => import('./views/Billing.vue'), meta: { title: '计费中心', icon: 'Wallet' } },
      { path: 'tickets', name: 'Tickets', component: () => import('./views/Tickets.vue'), meta: { title: '工单支持', icon: 'ChatDotRound' } },
      { path: 'token', name: 'Token', component: () => import('./views/Token.vue'), meta: { title: '接入码', icon: 'Key' } }
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('geo_token')) return '/login'
})

export default router
