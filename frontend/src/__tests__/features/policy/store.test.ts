import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { usePolicyStore } from '@/features/policy/store'
import { setSidecarEndpoint } from '@/lib/api/http'

describe('features/policy/store', () => {
  beforeEach(() => {
    setSidecarEndpoint({ port: 9999, token: 'test-token', version: '0.1.0' })
    usePolicyStore.setState({
      policies: [],
      selectedPolicyId: null,
      detail: null,
      loading: false,
      saving: false,
      error: null,
      scenarios: [],
      simulationResults: [],
      simulating: false,
    })
  })

  afterEach(() => {
    setSidecarEndpoint(null)
    vi.restoreAllMocks()
  })

  it('addRule adds a rule and sorts by priority', () => {
    usePolicyStore.setState({
      detail: {
        id: 'pol-1',
        name: 'default',
        mode: 'ask',
        rules: [],
      },
    })

    usePolicyStore.getState().addRule({
      priority: 20,
      scope: 'fs_path',
      matcher: '~/Desktop/**',
      effect: 'allow',
    })
    usePolicyStore.getState().addRule({
      priority: 10,
      scope: 'shell_command',
      matcher: '^rm.*',
      effect: 'deny',
      reason: 'dangerous',
    })

    const rules = usePolicyStore.getState().detail!.rules
    expect(rules).toHaveLength(2)
    // Sorted by priority: 10, 20
    expect(rules[0]!.priority).toBe(10)
    expect(rules[0]!.scope).toBe('shell_command')
    expect(rules[1]!.priority).toBe(20)
    expect(rules[1]!.scope).toBe('fs_path')
  })

  it('updateRule updates a specific rule', () => {
    usePolicyStore.setState({
      detail: {
        id: 'pol-1',
        name: 'default',
        mode: 'ask',
        rules: [
          {
            id: 'r1',
            policyId: 'pol-1',
            priority: 10,
            scope: 'fs_path',
            matcher: '~/**',
            effect: 'allow',
          },
        ],
      },
    })

    usePolicyStore.getState().updateRule('r1', { effect: 'deny', reason: 'updated' })
    const rule = usePolicyStore.getState().detail!.rules[0]!
    expect(rule.effect).toBe('deny')
    expect(rule.reason).toBe('updated')
  })

  it('removeRule removes a rule', () => {
    usePolicyStore.setState({
      detail: {
        id: 'pol-1',
        name: 'default',
        mode: 'ask',
        rules: [
          {
            id: 'r1',
            policyId: 'pol-1',
            priority: 10,
            scope: 'fs_path',
            matcher: '~/**',
            effect: 'allow',
          },
          {
            id: 'r2',
            policyId: 'pol-1',
            priority: 20,
            scope: 'tool_id',
            matcher: 'shell.exec',
            effect: 'ask',
          },
        ],
      },
    })

    usePolicyStore.getState().removeRule('r1')
    expect(usePolicyStore.getState().detail!.rules).toHaveLength(1)
    expect(usePolicyStore.getState().detail!.rules[0]!.id).toBe('r2')
  })

  it('addScenario adds a simulation scenario', () => {
    usePolicyStore.getState().addScenario({
      toolId: 'fs.write_file',
      args: { path: '/tmp/test.txt' },
    })
    expect(usePolicyStore.getState().scenarios).toHaveLength(1)
    expect(usePolicyStore.getState().scenarios[0]!.toolId).toBe('fs.write_file')
  })

  it('removeScenario removes a scenario by index', () => {
    usePolicyStore.getState().addScenario({ toolId: 'a', args: {} })
    usePolicyStore.getState().addScenario({ toolId: 'b', args: {} })
    usePolicyStore.getState().removeScenario(0)
    expect(usePolicyStore.getState().scenarios).toHaveLength(1)
    expect(usePolicyStore.getState().scenarios[0]!.toolId).toBe('b')
  })

  it('loadPolicies fetches policy list', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve([
            { id: 'pol-1', name: 'default', mode: 'ask' },
          ]),
      }),
    )

    await usePolicyStore.getState().loadPolicies()
    expect(usePolicyStore.getState().policies).toHaveLength(1)
    expect(usePolicyStore.getState().policies[0]!.name).toBe('default')
  })

  it('simulate calls API and stores results', async () => {
    usePolicyStore.setState({
      detail: {
        id: 'pol-1',
        name: 'default',
        mode: 'ask',
        rules: [],
      },
      scenarios: [{ toolId: 'fs.write_file', args: { path: '/tmp/test' } }],
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve([
            {
              tool_id: 'fs.write_file',
              effect: 'allow',
              rule_id: 'r1',
              reason: 'matched allow rule',
            },
          ]),
      }),
    )

    await usePolicyStore.getState().simulate()
    const results = usePolicyStore.getState().simulationResults
    expect(results).toHaveLength(1)
    expect(results[0]!.effect).toBe('allow')
    expect(results[0]!.reason).toBe('matched allow rule')
  })
})
