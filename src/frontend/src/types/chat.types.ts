// -- Source document from RAG retrieval --
export interface ChatSourceDocument {
  title: string
  year?: number
  similarity_score: number
  rerank_score?: number
}

// -- Pipeline stage durations (ms) --
export interface ChatTimings {
  classification_ms: number
  retrieval_ms?: number
  rerank_ms?: number
  generation_ms?: number
  total_ms: number
}

// -- Request / Response --
export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ChatResponse {
  response: string
  intent: string
  confidence: number
  session_id: string
  sources: ChatSourceDocument[]
  timings?: ChatTimings
  token_usage?: Record<string, number>
}

// -- Chat message (UI state) --
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  confidence?: number
  sources?: ChatSourceDocument[]
  timings?: ChatTimings
  token_usage?: Record<string, number>
  timestamp: Date
}

// -- SSE stream events --
export interface StreamEvent {
  type: 'chunk' | 'done' | 'error'
  content?: string
  intent?: string
  confidence?: number
  session_id?: string
  sources?: ChatSourceDocument[]
  timings?: ChatTimings
  token_usage?: Record<string, number>
}
