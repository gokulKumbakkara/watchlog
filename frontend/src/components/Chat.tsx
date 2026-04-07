import { useState, useRef, useEffect } from 'react'
import type { ChatMessage } from '../types'
import { makeSessionId } from '../api'
import { getToken } from '../auth'
import styles from './Chat.module.css'

const SESSION_ID = makeSessionId()

const SUGGESTED = [
  'What should I watch next?',
  'Any new seasons on my list?',
  'Remind me where I left off',
  'What happened in Season 1 of The Boys?',
]

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeTool])

  const send = async (text: string) => {
    const msg = text.trim()
    if (!msg || streaming) return

    setInput('')
    setStreaming(true)
    setActiveTool(null)

    const userMsg: ChatMessage = { id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(), role: 'user', content: msg }
    setMessages(prev => [...prev, userMsg])

    const assistantId = crypto.randomUUID ? crypto.randomUUID() : (Date.now() + 1).toString()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true }])

    try {
      const token = getToken()
      const res = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: msg, session_id: SESSION_ID }),
      })

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          const data = JSON.parse(part.slice(6))

          if (data.type === 'token') {
            setMessages(prev =>
              prev.map(m => m.id === assistantId ? { ...m, content: m.content + data.content } : m)
            )
          } else if (data.type === 'tool_call') {
            setActiveTool(data.tool)
          } else if (data.type === 'done') {
            setActiveTool(null)
            setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, streaming: false } : m))
          } else if (data.type === 'error') {
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: `Error: ${data.content}`, streaming: false } : m
            ))
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: 'Connection error. Is the server running?', streaming: false } : m
      ))
    } finally {
      setStreaming(false)
      setActiveTool(null)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className={styles.panel}>
      <div className={styles.messages}>
        {isEmpty ? (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>✦</div>
            <h3>WatchLog AI</h3>
            <p>Ask me anything about your watchlist</p>
            <div className={styles.suggestions}>
              {SUGGESTED.map(s => (
                <button key={s} className={styles.chip} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`${styles.msg} ${styles[m.role]}`}>
              {m.role === 'assistant' && (
                <div className={styles.avatar}>✦</div>
              )}
              <div className={styles.bubble}>
                <span className={styles.text}>{m.content}</span>
                {m.streaming && <span className={styles.cursor} />}
              </div>
            </div>
          ))
        )}

        {activeTool && (
          <div className={styles.toolPill}>
            <span className={styles.toolDot} />
            Using {activeTool.replace(/_/g, ' ')}…
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className={styles.inputArea}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about your watchlist…"
          rows={1}
          disabled={streaming}
        />
        <button
          className={`btn btn-primary ${styles.sendBtn}`}
          onClick={() => send(input)}
          disabled={streaming || !input.trim()}
        >
          {streaming ? <span className={styles.sendSpinner} /> : (
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.903 6.256H13.5a.75.75 0 010 1.5H4.182l-1.903 6.256a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
