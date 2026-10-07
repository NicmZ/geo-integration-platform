<template>
  <el-container class="layout">
    <!-- PC 端固定侧栏 -->
    <el-aside v-if="!isMobile" width="220px" class="aside">
      <div class="logo">GEO 优化平台</div>
      <el-menu :default-active="$route.path" router background-color="#1d2535" text-color="#aeb6c5"
               active-text-color="#409EFF" class="menu">
        <el-menu-item v-for="m in menus" :key="m.path" :index="'/' + m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header" :height="isMobile ? '52px' : '60px'">
        <div class="title">
          <el-icon v-if="isMobile" class="burger" @click="drawerOpen = true"><menu /></el-icon>
          {{ $route.meta.title }}
        </div>
        <div class="right">
          <el-tag type="warning" effect="plain" :size="isMobile ? 'small' : 'default'" style="margin-right:12px">¥{{ profile.balance }}</el-tag>
          <el-dropdown @command="onCommand">
            <span class="user">{{ profile.username || '用户' }}<el-icon><arrow-down /></el-icon></span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main"><router-view /></el-main>
    </el-container>

    <!-- 移动端抽屉菜单 -->
    <el-drawer v-model="drawerOpen" direction="ltr" size="220px" :with-header="false" class="mobile-drawer">
      <div class="logo" style="background:#1d2535;color:#fff">GEO 优化平台</div>
      <el-menu :default-active="$route.path" router background-color="#1d2535" text-color="#aeb6c5"
               active-text-color="#409EFF" class="menu" style="height:100%"
               @select="drawerOpen = false">
        <el-menu-item v-for="m in menus" :key="m.path" :index="'/' + m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Menu } from '@element-plus/icons-vue'
import api from '../api'

const route = useRoute()
const router = useRouter()
const profile = ref({ username: '', balance: 0 })
const isMobile = ref(window.innerWidth < 768)
const drawerOpen = ref(false)

const menus = router.options.routes[1].children.map(r => ({
  path: r.path, title: r.meta.title, icon: r.meta.icon
}))

function onResize() { isMobile.value = window.innerWidth < 768 }

function loadProfile() {
  api.get('/api/users/profile/').then(d => {
    profile.value = { username: d.username, balance: d.balance }
    localStorage.setItem('geo_profile', JSON.stringify(d))
  }).catch(() => {})
}

function onCommand(cmd) {
  if (cmd === 'logout') {
    api.post('/api/users/logout/').catch(() => {})
    localStorage.removeItem('geo_token')
    router.push('/login')
  }
}

onMounted(() => {
  loadProfile()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
watch(() => route.path, loadProfile)
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1d2535; }
.logo { color: #fff; font-size: 18px; font-weight: 700; padding: 20px 16px; letter-spacing: 2px; }
.menu { border-right: none; }
.header { background: #fff; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0,21,41,.08); padding: 0 14px; }
.title { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.burger { font-size: 20px; cursor: pointer; margin-right: 4px; }
.right { display: flex; align-items: center; }
.user { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.main { padding: 16px; overflow: auto; }
@media (max-width: 768px) {
  .main { padding: 10px; }
  .title { font-size: 15px; }
}
</style>
