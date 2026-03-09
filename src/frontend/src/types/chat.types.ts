export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ChatResponse {
  response: string
  intent: string
  confidence: number
  session_id: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  confidence?: number
  timestamp: Date
}

export interface StreamEvent {
  type: 'chunk' | 'done' | 'error'
  content?: string
  intent?: string
  confidence?: number
  session_id?: string
}
