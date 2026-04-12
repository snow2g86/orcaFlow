import { useCallback, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'

type ChatInputProps = {
  onSend: (text: string) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    inputRef.current?.focus()
  }, [text, disabled, onSend])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <div className="chat-input">
      <textarea
        ref={inputRef}
        className="chat-input__textarea"
        placeholder="Tell OrcaFlow what to do..."
        value={text}
        onChange={(e) => {
          setText(e.target.value)
        }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={2}
      />
      <Button
        variant="primary"
        size="sm"
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
      >
        Send
      </Button>
    </div>
  )
}
