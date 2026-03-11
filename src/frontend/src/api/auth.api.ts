import apiClient from './client'
import type {
  UserLoginRequest,
  AdminLoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
} from '@/types'

export function loginUser(
  credentials: UserLoginRequest
): Promise<LoginResponse> {
  return apiClient
    .post<LoginResponse>('/auth/token', credentials)
    .then((r) => r.data)
}

export function loginAdmin(
  credentials: AdminLoginRequest
): Promise<LoginResponse> {
  return apiClient
    .post<LoginResponse>('/auth/admin/token', credentials)
    .then((r) => r.data)
}

export function register(data: RegisterRequest): Promise<RegisterResponse> {
  return apiClient
    .post<RegisterResponse>('/auth/register', data)
    .then((r) => r.data)
}
