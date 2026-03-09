export interface HealthComponent {
  loaded?: boolean
  connected?: boolean
  model_loaded?: boolean
  memory_mb?: number
  pool_available?: number
}

export interface HealthResponse {
  status: string
  version: string
  components: {
    llm: HealthComponent
    database: HealthComponent
    embeddings: HealthComponent
  }
  timestamp: string
}
