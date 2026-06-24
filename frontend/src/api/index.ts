/**
 * Desktop API — 使用共享 createApi 工厂 + axios 适配器
 */
import http from './http'
import { createApi } from '@/shared/api/createApi'

// axios → HttpClient 适配器
const axiosAdapter = {
  get: (path: string, params?: Record<string, any>) =>
    http.get(path, { params: params?.params ?? params }).then((r) => r.data),
  post: (path: string, body?: any, params?: Record<string, any>) =>
    http.post(path, body, { params: params?.params ?? params }).then((r) => r.data),
  patch: (path: string, body?: any, params?: Record<string, any>) =>
    http.patch(path, body, { params: params?.params ?? params }).then((r) => r.data),
  put: (path: string, body?: any, params?: Record<string, any>) =>
    http.put(path, body, { params: params?.params ?? params }).then((r) => r.data),
  del: (path: string, params?: Record<string, any>) =>
    http.delete(path, { params: params?.params ?? params }).then((r) => r.data),
  postForm: (path: string, fd: FormData) =>
    http.post(path, fd).then((r) => r.data),
  request: (path: string, opts?: { method?: string; data?: any; params?: Record<string, any>; headers?: Record<string, string> }) =>
    http.request({ url: path, method: opts?.method || 'GET', data: opts?.data, params: opts?.params, headers: opts?.headers }).then((r) => r.data),
}

export const api = createApi(axiosAdapter)
