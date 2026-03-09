import apiClient from './client'
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
} from '@/types'

export function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiClient
    .post<LoginResponse>('/auth/token', credentials)
    .then((r) => r.data)
}

export function register(data: RegisterRequest): Promise<RegisterResponse> {
  return apiClient
    .post<RegisterResponse>('/auth/register', data)
    .then((r) => r.data)
}
