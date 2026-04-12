type DiffPreviewProps = {
  data: Record<string, unknown>
}

export function DiffPreview({ data }: DiffPreviewProps) {
  return (
    <div className="diff-preview">
      <pre className="diff-preview__content">{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}
