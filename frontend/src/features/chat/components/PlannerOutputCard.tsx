import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { PlannerOutput } from '@/types/chat.types'

type PlannerOutputCardProps = {
  output: PlannerOutput
  onExecute?: () => void
  executing?: boolean
}

export function PlannerOutputCard({ output, onExecute, executing }: PlannerOutputCardProps) {
  const confidenceVariant =
    output.confidence === 'high'
      ? 'success' as const
      : output.confidence === 'medium'
        ? 'warning' as const
        : 'error' as const

  return (
    <Card className="planner-output-card">
      <CardHeader>
        <div className="planner-output-card__header">
          <strong>Plan</strong>
          <Badge variant={confidenceVariant}>{output.confidence}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="planner-output-card__field">
          <label>Intent</label>
          <p>{output.intent}</p>
        </div>
        <div className="planner-output-card__field">
          <label>Reasoning</label>
          <p>{output.reasoning}</p>
        </div>
        {output.expectedEffects.length > 0 && (
          <div className="planner-output-card__field">
            <label>Expected Effects</label>
            <ul>
              {output.expectedEffects.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        {output.questions.length > 0 && (
          <div className="planner-output-card__field">
            <label>Questions</label>
            <ul>
              {output.questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="planner-output-card__field">
          <label>Workflow YAML</label>
          <pre className="planner-output-card__yaml">{output.workflowYaml}</pre>
        </div>
        {onExecute && (
          <Button
            variant="primary"
            onClick={onExecute}
            disabled={executing}
          >
            {executing ? 'Executing...' : 'Execute this workflow'}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
