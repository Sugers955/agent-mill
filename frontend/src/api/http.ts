import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/', timeout: 30000 })

http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('access_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status
    const data = err.response?.data
    let msg = err.message
    if (typeof data?.detail === 'string') msg = data.detail
    else if (Array.isArray(data?.detail)) {
      msg = data.detail
        .map((d: any) => `${(d.loc || []).slice(-1)[0] || ''}: ${d.msg}`)
        .join('; ')
    } else if (data?.message) msg = data.message
    if (status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (location.pathname !== '/login') location.href = '/login'
    } else {
      ElMessage.error(msg || '请求失败')
    }
    return Promise.reject(err)
  },
)

export default http
