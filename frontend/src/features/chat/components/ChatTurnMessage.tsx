import type { ConversationTurn } from '@/types/chat.types'

type ChatTurnMessageProps = {
  turn: ConversationTurn
}

export function ChatTurnMessage({ turn }: ChatTurnMessageProps) {
  return (
    <div className="chat-turn">
      <div className="chat-turn__user">
        <span className="chat-turn__role">You</span>
        <p className="chat-turn__text">{turn.userText}</p>
      </div>
      {turn.plannerOutput && (
        <div className="chat-turn__assistant">
          <span className="chat-turn__role">OrcaFlow</span>
          <p className="chat-turn__text">{turn.plannerOutput.intent}</p>
        </div>
      )}
    </div>
  )
}
