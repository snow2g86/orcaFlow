// Policy feature types — schema.md §3.8, §3.9

export type PolicyRuleScope =
  | 'fs_path'
  | 'shell_command'
  | 'network_host'
  | 'os_api'
  | 'tool_id'

export type PolicyRuleEffect = 'allow' | 'deny' | 'ask' | 'dry_run_only'

export type PolicyRule = {
  id: string
  policyId: string
  priority: number
  scope: PolicyRuleScope
  matcher: string
  effect: PolicyRuleEffect
  reason?: string | undefined
}

export type PolicyDetail = {
  id: string
  name: string
  mode: 'strict' | 'ask' | 'trusted'
  rules: PolicyRule[]
  requireDryRunFor?: string[] | undefined
  autoApproveReversible?: boolean | undefined
}

export type SimulationScenario = {
  toolId: string
  args: Record<string, unknown>
}

export type SimulationResult = {
  toolId: string
  effect: PolicyRuleEffect
  ruleId: string | null
  reason: string
}
