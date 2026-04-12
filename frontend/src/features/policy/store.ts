// Policy Zustand store — 정책 목록/선택/편집/시뮬레이션.

import yaml from 'js-yaml'
import { create } from 'zustand'

import type {
  PolicyDetail,
  PolicyRule,
  PolicyRuleEffect,
  PolicyRuleScope,
  SimulationResult,
  SimulationScenario,
} from '@/features/policy/types'
import * as policyApi from '@/lib/api/policy'
import type { PolicySummary } from '@/types/policy.types'

type PolicyState = {
  policies: PolicySummary[]
  selectedPolicyId: string | null
  detail: PolicyDetail | null
  loading: boolean
  saving: boolean
  error: string | null

  // Simulation
  scenarios: SimulationScenario[]
  simulationResults: SimulationResult[]
  simulating: boolean

  // Actions
  loadPolicies: () => Promise<void>
  selectPolicy: (id: string) => Promise<void>
  addRule: (rule: Omit<PolicyRule, 'id' | 'policyId'>) => void
  updateRule: (ruleId: string, update: Partial<PolicyRule>) => void
  removeRule: (ruleId: string) => void
  savePolicy: () => Promise<void>
  addScenario: (scenario: SimulationScenario) => void
  removeScenario: (index: number) => void
  simulate: () => Promise<void>
}

let ruleCounter = 0

export const usePolicyStore = create<PolicyState>((set, get) => ({
  policies: [],
  selectedPolicyId: null,
  detail: null,
  loading: false,
  saving: false,
  error: null,
  scenarios: [],
  simulationResults: [],
  simulating: false,

  loadPolicies: async () => {
    try {
      const policies = await policyApi.listPolicies()
      set({ policies })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Failed to load policies' })
    }
  },

  selectPolicy: async (id) => {
    set({ loading: true, error: null, selectedPolicyId: id })
    try {
      const raw = await policyApi.getPolicy(id)
      const detail: PolicyDetail = {
        id: raw.id,
        name: raw.name,
        mode: raw.mode as PolicyDetail['mode'],
        rules: raw.rules.map((r) => {
          const rule: PolicyRule = {
            id: r.id,
            policyId: r.policyId,
            priority: r.priority,
            scope: r.scope as PolicyRuleScope,
            matcher: r.matcher,
            effect: r.effect as PolicyRuleEffect,
          }
          if (r.reason) rule.reason = r.reason
          return rule
        }),
        requireDryRunFor: raw.requireDryRunFor,
        autoApproveReversible: raw.autoApproveReversible,
      }
      set({ detail, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to load policy',
        loading: false,
      })
    }
  },

  addRule: (rule) => {
    const { detail } = get()
    if (!detail) return
    ruleCounter += 1
    const newRule: PolicyRule = {
      id: `rule-new-${ruleCounter.toString()}`,
      policyId: detail.id,
      ...rule,
    }
    set({
      detail: {
        ...detail,
        rules: [...detail.rules, newRule].sort((a, b) => a.priority - b.priority),
      },
    })
  },

  updateRule: (ruleId, update) => {
    const { detail } = get()
    if (!detail) return
    set({
      detail: {
        ...detail,
        rules: detail.rules
          .map((r) => (r.id === ruleId ? { ...r, ...update } : r))
          .sort((a, b) => a.priority - b.priority),
      },
    })
  },

  removeRule: (ruleId) => {
    const { detail } = get()
    if (!detail) return
    set({
      detail: {
        ...detail,
        rules: detail.rules.filter((r) => r.id !== ruleId),
      },
    })
  },

  savePolicy: async () => {
    const { detail } = get()
    if (!detail) return
    set({ saving: true, error: null })
    try {
      const yamlObj = {
        policy: detail.name,
        mode: detail.mode,
        rules: detail.rules.map((r) => ({
          priority: r.priority,
          scope: r.scope,
          matcher: r.matcher,
          effect: r.effect,
          ...(r.reason ? { reason: r.reason } : {}),
        })),
      }
      const yamlStr = yaml.dump(yamlObj, { indent: 2, noRefs: true })
      await policyApi.updatePolicy(detail.id, yamlStr)
      set({ saving: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Failed to save policy',
        saving: false,
      })
    }
  },

  addScenario: (scenario) => {
    const { scenarios } = get()
    set({ scenarios: [...scenarios, scenario] })
  },

  removeScenario: (index) => {
    const { scenarios } = get()
    set({ scenarios: scenarios.filter((_, i) => i !== index) })
  },

  simulate: async () => {
    const { detail, scenarios } = get()
    if (!detail || scenarios.length === 0) return
    set({ simulating: true, error: null })
    try {
      const results = await policyApi.simulatePolicy(detail.id, {
        scenarios,
      })
      set({
        simulationResults: results.map((r) => ({
          toolId: r.toolId,
          effect: r.effect as PolicyRuleEffect,
          ruleId: r.ruleId,
          reason: r.reason,
        })),
        simulating: false,
      })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : 'Simulation failed',
        simulating: false,
      })
    }
  },
}))
