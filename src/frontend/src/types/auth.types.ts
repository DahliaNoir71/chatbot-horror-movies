export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number // Durée en secondes (E3: JWT_EXPIRE_MINUTES)
}

export interface RegisterRequest {
  username: string // 3-50 chars, alphanumeric + _ -
  password: string // Min 8 chars
}

export interface RegisterResponse {
  username: string
  message: string
}

export interface User {
  username: string
}
