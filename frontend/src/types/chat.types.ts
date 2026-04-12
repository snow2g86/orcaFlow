// schema.md §3.17 + planner output — Chat 타입

export type ConversationTurn = {
  id: string
  sessionId: string
  userText: string
  plannerOutput?: PlannerOutput
  createdAt: string
}

export type PlannerOutput = {
  intent: string
  reasoning: string
  workflowYaml: string
  expectedEffects: string[]
  confidence: 'low' | 'medium' | 'high'
  questions: string[]
}
