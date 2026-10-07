import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/', timeout: 60000 })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('geo_token')
  if (token) cfg.headers.Authorization = 'Bearer ' + token
  return cfg
})

api.interceptors.response.use(
  resp => {
    const body = resp.data
    if (body && typeof body.code !== 'undefined' && body.code !== 0) {
      ElMessage.error(body.msg || '操作失败')
      return Promise.reject(body)
    }
    return body.data !== undefined ? body.data : body
  },
  err => {
    const resp = err.response
    if (resp && resp.status === 401) {
      localStorage.removeItem('geo_token')
      if (location.pathname !== '/login') location.href = '/login'
    } else {
      const msg = (resp && resp.data && resp.data.msg) || err.message || '网络错误'
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export default api
