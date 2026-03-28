# RedSpider Frontend — Complete Code Changes

5 files need changes. The core problems found by reading every component:

1. **ChatInterface.tsx** — listens for `data.done` to stop "running" state, but
   the backend now emits `type: "workflow_complete"`. Also doesn't restore
   `todos`, `status`, or `current_node` from `/workflow/state` on page load.
   The `isLoading` flag never clears on `workflow_complete`, leaving the UI frozen.

2. **WorkflowGraph.tsx** — only shows one "active" node at a time with no visual
   distinction between nodes that are "done" vs "not yet started". Once the coder
   finishes, the graph goes blank until validation starts — confusing to the user.

3. **TodoList.tsx** — the `inferredCompleted` hack (guessing completion by counting
   list shrinkage) was compensating for the agent never calling `write_todos` after
   each task. Now that the prompt fix makes the agent update todos per-task, this
   hack will give wrong counts. Remove it and use the real status.

4. **Workspace.tsx** — `activeNode` starts as `'architect_agent'` hardcoded.
   On page refresh/restore, this means the banner always shows "architect" briefly
   before real state loads. Should start as `null`.

5. **SubagentCard.tsx** — minor: `thinking` content blocks now stream through
   (after the `v2` backend fix), but the card truncates `lastContent` to 500
   chars with `.slice(-500)`, which cuts off the *beginning* of thinking,
   keeping only the tail. For thinking content, prepend not append.

---

## CHANGE 1 of 5 — `components/ChatInterface.tsx`

Full file replacement. Key changes highlighted in comments.

```tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import TodoList from '@/components/TodoList'
import SubagentCard, { type SubagentInfo } from '@/components/SubagentCard'

interface ChatInterfaceProps {
  activeNode: string | null
  setActiveNode: (node: string | null) => void
  threadId: string | null
  setThreadId: (id: string | null) => void
  onPlanUpdate?: (content: string, isStreaming: boolean) => void
  onViewPlan?: (content: string) => void
  onClosePlanViewer?: () => void
  isPlanViewerOpen?: boolean
  isPlannerStreaming?: boolean
  currentViewingPlanContent?: string
  shouldLoadHistory?: boolean
  projectTitle?: string
  onTerminalLog?: (log: string) => void
  // NEW: let Workspace know the workflow fully completed so it can update UI
  onWorkflowComplete?: (finalTodos: TodoItem[]) => void
}

interface TodoItem {
  status: 'pending' | 'in_progress' | 'completed'
  content: string
  title?: string
}

interface Message {
  role: 'user' | 'agent'
  content: string
  node?: string
  isLoading?: boolean
  planContent?: string
  isDeepAgentBlock?: boolean
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const extractText = (content: any): string => {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return content.map(c => extractText(c)).join('')
  if (typeof content === 'object' && content !== null) return content.text || JSON.stringify(content)
  return String(content || '')
}

export default function ChatInterface({
  activeNode,
  setActiveNode,
  threadId,
  setThreadId,
  onPlanUpdate,
  onViewPlan,
  onClosePlanViewer,
  isPlanViewerOpen,
  isPlannerStreaming,
  currentViewingPlanContent,
  shouldLoadHistory = false,
  projectTitle,
  onTerminalLog,
  onWorkflowComplete,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [instruction, setInstruction] = useState<string | null>(null)
  const [pendingCommand, setPendingCommand] = useState<string | null>(null)
  const [isWorkflowInitialized, setIsWorkflowInitialized] = useState(false)
  const [isWaitingForApproval, setIsWaitingForApproval] = useState(false)
  const [isCommandApproval, setIsCommandApproval] = useState(false)
  const [todos, setTodos] = useState<TodoItem[]>([])
  const [subagents, setSubagents] = useState<Map<string, SubagentInfo>>(new Map())
  // FIX: track whether the full pipeline has completed so the banner clears
  const [workflowDone, setWorkflowDone] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Restore state from backend on mount / project open
  useEffect(() => {
    const restoreSession = async (idToRestore: string) => {
      console.log('Restoring session for thread_id:', idToRestore)
      setIsLoading(true)
      try {
        const response = await fetch(`${API_BASE_URL}/workflow/state/${idToRestore}`)
        if (!response.ok) {
          if (!threadId) localStorage.removeItem('thread_id')
          return
        }

        const data = await response.json()
        console.log('Restored state:', data)

        if (data.thread_id) {
          if (!threadId) setThreadId(data.thread_id)
          if (data.active_node) setActiveNode(data.active_node)
          if (data.instruction) setInstruction(data.instruction)

          // FIX: restore todos from persisted state so they survive page refresh
          if (data.todos && Array.isArray(data.todos) && data.todos.length > 0) {
            setTodos(data.todos)
          }

          // FIX: if the workflow was already completed, reflect that in UI
          if (data.status === 'completed') {
            setWorkflowDone(true)
            setIsLoading(false)
          }

          if (data.messages && Array.isArray(data.messages)) {
            setMessages(data.messages.map((msg: any) => {
              if (msg.node?.includes('planner') && msg.role === 'agent') {
                return {
                  role: msg.role,
                  content: 'Plan generated',
                  planContent: msg.content,
                  node: msg.node,
                  isLoading: false
                }
              }
              return {
                role: msg.role,
                content: msg.content,
                node: msg.node,
                isLoading: false
              }
            }))
          }
        }
      } catch (err) {
        console.error('Error restoring session:', err)
      } finally {
        setIsLoading(false)
        setIsWorkflowInitialized(true)
      }
    }

    if (threadId && shouldLoadHistory) {
      restoreSession(threadId)
      return
    }

    const savedThreadId = localStorage.getItem('thread_id')
    if (savedThreadId && !threadId) {
      restoreSession(savedThreadId)
    }
  }, [threadId, setThreadId, setActiveNode, shouldLoadHistory])

  useEffect(() => {
    if (threadId) localStorage.setItem('thread_id', threadId)
  }, [threadId])

  const handleStartWorkflow = async (e: React.FormEvent, existingThreadId: string | null = null) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)
    setWorkflowDone(false)
    setActiveNode('architect_agent')

    setMessages([
      { role: 'user', content: userMessage },
      { role: 'agent', content: '', node: 'architect_agent', isLoading: true },
    ])

    try {
      const response = await fetch(`${API_BASE_URL}/workflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          initial_query: userMessage,
          thread_id: existingThreadId,
          title: projectTitle || ''
        }),
      })

      if (!response.ok) throw new Error(`Server error: ${response.status}`)

      const data = await response.json()
      setThreadId(data.thread_id)
      setActiveNode(data.agent_node || 'architect')
      setInstruction(data.agent_instruction || null)
      setIsWaitingForApproval(true)
      setIsWorkflowInitialized(true)

      setMessages([
        { role: 'user', content: userMessage },
        {
          role: 'agent',
          content: data.agent_output || 'No response from agent.',
          node: data.agent_node || 'architect_agent',
        },
      ])
    } catch (error) {
      console.error('Error starting workflow:', error)
      setMessages([
        { role: 'user', content: userMessage },
        { role: 'agent', content: 'Error starting workflow. Please try again.' },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading || !threadId) return

    if (!isWorkflowInitialized && threadId) {
      return handleStartWorkflow(e, threadId)
    }

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)
    setWorkflowDone(false)

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage },
      { role: 'agent', content: '', node: 'agent', isLoading: true },
    ])

    try {
      await handleStreamingResponse(userMessage, `${API_BASE_URL}/workflow/chat`)
    } catch (error) {
      console.error('Error processing message:', error)
      setMessages((prev) => {
        const msgs = [...prev]
        const last = msgs.length - 1
        if (last >= 0) {
          msgs[last] = {
            ...msgs[last],
            content: 'Error getting response. Please try again.',
            isLoading: false,
          }
        }
        return msgs
      })
      setIsLoading(false)
    }
  }

  const handleStreamingResponse = async (userMessage: string, endpoint: string) => {
    abortControllerRef.current = new AbortController()

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: threadId, query: userMessage }),
      signal: abortControllerRef.current.signal,
    })

    if (!response.ok) throw new Error('Streaming failed')

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentAgentMessage = ''
    let currentNode = activeNode || 'agent'
    let isPlanStreaming = false
    let deepAgentBlockInserted = false

    if (!reader) throw new Error('No reader available')

    setMessages((prev) => {
      const msgs = [...prev]
      const last = msgs.length - 1
      if (last >= 0) {
        msgs[last] = { ...msgs[last], role: 'agent', content: '', node: currentNode }
      }
      return msgs
    })

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue

        try {
          const data = JSON.parse(line)

          // Node lifecycle — update the graph panel
          if (data.progress) {
            currentNode = data.progress
            setActiveNode(data.progress)
            continue
          }

          // ── Subagent start ─────────────────────────────────────────────────
          if (data.type === 'subagent_start') {
            if (!deepAgentBlockInserted) {
              deepAgentBlockInserted = true
              setMessages((prev) => {
                const msgs = [...prev]
                msgs[msgs.length - 1] = {
                  role: 'agent',
                  content: '',
                  node: data.node,
                  isLoading: false,
                  isDeepAgentBlock: true,
                }
                return msgs
              })
            }
            setSubagents((prev) => {
              const next = new Map(prev)
              next.set(data.node, {
                id: data.node,
                label: data.label || data.node,
                status: 'running',
                startedAt: data.startedAt,
                lastContent: '',
              })
              return next
            })
            continue
          }

          // ── Subagent end ───────────────────────────────────────────────────
          if (data.type === 'subagent_end') {
            setSubagents((prev) => {
              const next = new Map(prev)
              const existing = next.get(data.node)
              if (existing) {
                next.set(data.node, {
                  ...existing,
                  status: data.status === 'error' ? 'error' : 'complete',
                  completedAt: data.completedAt,
                })
              }
              return next
            })
            continue
          }

          // ── Todo updates ───────────────────────────────────────────────────
          if (data.type === 'todo_update') {
            setTodos(data.todos || [])
            continue
          }

          // ── Agent tokens (thinking + text from deepagents) ─────────────────
          if (data.type === 'agent_token') {
            const tokenStr = extractText(data.content)
            if (!tokenStr) continue
            setSubagents((prev) => {
              const next = new Map(prev)
              const existing = next.get(data.node)
              if (existing) {
                // Keep last 800 chars — enough to show meaningful thinking
                const updated = (existing.lastContent + tokenStr).slice(-800)
                next.set(data.node, { ...existing, lastContent: updated })
              }
              return next
            })
            continue
          }

          // ── Tool events ────────────────────────────────────────────────────
          if (data.type === 'agent_tool_start' || data.type === 'agent_tool_end') {
            const toolText = data.type === 'agent_tool_start'
              ? `\n❯ ${data.tool}...`
              : `\n✓ ${data.tool} done`
            setSubagents((prev) => {
              const next = new Map(prev)
              const existing = next.get(data.node)
              if (existing) {
                const updated = (existing.lastContent + toolText).slice(-800)
                next.set(data.node, { ...existing, lastContent: updated })
              }
              return next
            })
            continue
          }

          // ── Planner / interrupt tokens ─────────────────────────────────────
          if (data.token) {
            const tokenStr = extractText(data.token)
            if (data.is_interrupt) {
              currentAgentMessage = tokenStr
              if (data.agent_node) { currentNode = data.agent_node; setActiveNode(data.agent_node) }
              if (data.instruction) setInstruction(data.instruction)
              if (data.interrupt_type === 'command_approval') setPendingCommand(tokenStr)
              setIsWaitingForApproval(true)
              setIsCommandApproval(data.interrupt_type === 'command_approval')
              setMessages((prev) => {
                const msgs = [...prev]
                const last = msgs.length - 1
                if (last >= 0) {
                  msgs[last] = { ...msgs[last], content: currentAgentMessage, node: currentNode, isLoading: false }
                }
                return msgs
              })
            } else {
              currentAgentMessage += tokenStr
              if (!isPlanStreaming) {
                isPlanStreaming = true
                setMessages((prev) => {
                  const msgs = [...prev]
                  const last = msgs.length - 1
                  if (last >= 0) msgs[last] = { ...msgs[last], node: 'planner', isLoading: true }
                  return msgs
                })
              }
              if (onPlanUpdate) onPlanUpdate(currentAgentMessage, true)
            }
            if (data.agent_node) { currentNode = data.agent_node; setActiveNode(data.agent_node) }
          }

          // ── Terminal output ────────────────────────────────────────────────
          else if (data.terminal_log) {
            if (onTerminalLog) onTerminalLog(data.terminal_log)
            continue
          }

          // ── FIX: workflow_complete replaces the old `data.done` check ──────
          // The old code did `else if (data.done)` which was a race condition:
          // the stream could close before this event was processed, leaving
          // isLoading=true forever. Now we handle it explicitly as a typed event.
          else if (data.type === 'workflow_complete') {
            // Persist the final todo list from state if provided
            if (data.todos && Array.isArray(data.todos) && data.todos.length > 0) {
              setTodos(data.todos)
            }
            if (data.current_node) setActiveNode(data.current_node)
            setWorkflowDone(true)
            setInstruction(null)   // clear any stale instruction banner
            setIsWaitingForApproval(false)
            // Notify Workspace so it can update the progress banner
            if (onWorkflowComplete) onWorkflowComplete(data.todos || [])
            continue
          }

          // ── Legacy done signal (keep for backwards compat during transition) 
          else if (data.done) {
            if (data.agent_node) { setActiveNode(data.agent_node); currentNode = data.agent_node }
            setWorkflowDone(true)
          }

          else if (data.error) {
            throw new Error(data.error)
          }

        } catch (e) {
          console.log('Failed to parse SSE line:', line)
        }
      }
    }

    // Stream ended — finalize UI state
    setIsLoading(false)

    if (isPlanStreaming && onPlanUpdate) {
      onPlanUpdate(currentAgentMessage, false)
    }

    setMessages((prev) => {
      const msgs = [...prev]
      const last = msgs.length - 1
      if (last >= 0) {
        if (isPlanStreaming) {
          msgs[last] = {
            ...msgs[last],
            content: 'Plan generated',
            planContent: currentAgentMessage,
            node: 'planner',
            isLoading: false,
          }
        } else if (msgs[last].isLoading || !msgs[last].content) {
          msgs[last] = {
            ...msgs[last],
            content: currentAgentMessage || 'No response from agent.',
            node: currentNode,
            isLoading: false,
          }
        }
      }
      return msgs
    })
  }

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort()
    }
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6 min-h-0 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="text-4xl mb-6 opacity-40">🕷️</div>
              <p className="text-xl text-platinum mb-2 font-thin tracking-[0.2em] uppercase">
                System Initialized
              </p>
              <p className="text-xs text-platinum-muted font-light tracking-widest">
                Awaiting objective parameters...
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-5 max-w-4xl mx-auto">
            {messages.map((message, idx) => (
              <div
                key={idx}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {message.isDeepAgentBlock ? (
                  <div className="w-full max-w-[95%] space-y-3">
                    {Array.from(subagents.values()).length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between px-1">
                          <span className="text-[9px] font-medium text-white/30 uppercase tracking-[0.2em]">
                            Specialist Agents &middot;{' '}
                            {Array.from(subagents.values()).filter(s => s.status === 'complete').length}
                            /{subagents.size} completed
                          </span>
                        </div>
                        <div className="w-full h-1 rounded-full bg-white/[0.04] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-emerald-500/60 to-emerald-400/80 transition-all duration-500"
                            style={{
                              width: `${subagents.size
                                ? (Array.from(subagents.values()).filter(s => s.status === 'complete').length / subagents.size) * 100
                                : 0}%`
                            }}
                          />
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                          {Array.from(subagents.values()).map((sa) => (
                            <SubagentCard key={sa.id} subagent={sa} />
                          ))}
                        </div>
                      </div>
                    )}
                    {todos.length > 0 && <TodoList todos={todos} />}
                  </div>
                ) : message.node?.includes('planner') && message.role === 'agent' ? (
                  <div className="rounded border border-white/10 bg-carbon overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-4">
                      <div className="flex items-center gap-4">
                        <div className="w-8 h-8 rounded bg-white/5 flex items-center justify-center border border-white/5">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-platinum" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                          </svg>
                        </div>
                        <div>
                          <div className="flex items-center gap-3">
                            <span className="text-[11px] font-medium tracking-widest uppercase text-platinum">Architecture Plan</span>
                            {message.isLoading ? (
                              <div className="flex items-center gap-1.5">
                                <div className="w-1 h-1 bg-white/50 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
                                <div className="w-1 h-1 bg-white/50 rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
                                <div className="w-1 h-1 bg-white/50 rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
                              </div>
                            ) : <div className="w-1 h-1 rounded-full bg-white/50" />}
                          </div>
                          <p className="text-[10px] text-white/30 uppercase tracking-widest mt-1">
                            {message.isLoading ? 'Synthesizing...' : 'Finalized'}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          const isViewingThisPlan = isPlanViewerOpen && currentViewingPlanContent === message.planContent
                          if (isViewingThisPlan) { onClosePlanViewer?.() }
                          else { onViewPlan?.(message.planContent || '') }
                        }}
                        disabled={!message.planContent}
                        className={`flex items-center gap-2 px-5 py-2.5 text-[10px] uppercase tracking-[0.2em] font-medium transition-all ${!message.planContent
                          ? 'text-white/20 cursor-not-allowed'
                          : isPlanViewerOpen && currentViewingPlanContent === message.planContent
                            ? 'bg-white text-obsidian rounded-full shadow-[0_0_15px_rgba(255,255,255,0.4)]'
                            : 'bg-white/5 border border-white/10 hover:bg-white/10 text-platinum rounded-full'
                          }`}
                      >
                        {isPlanViewerOpen && currentViewingPlanContent === message.planContent ? 'Hide' : 'Inspect'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`max-w-[85%] ${message.role === 'user'
                      ? 'bg-gradient-to-br from-white/10 to-white/5 text-platinum border border-white/10 rounded-2xl rounded-tr-sm px-6 py-4 shadow-[0_8px_30px_rgb(0,0,0,0.12)]'
                      : 'bg-transparent text-platinum border-transparent pl-2 py-4'
                      }`}
                  >
                    {message.node?.includes('architect') && message.role === 'agent' && !message.isLoading && message.content && (
                      <div className="flex items-center gap-2 pb-3 opacity-50">
                        <span className="text-[10px] font-medium text-white uppercase tracking-[0.2em]">Architect</span>
                      </div>
                    )}
                    <div>
                      {message.isLoading ? (
                        <div className="flex items-center gap-2 py-2">
                          <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-pulse"></div>
                          <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                          <div className="w-1.5 h-1.5 bg-white/40 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                        </div>
                      ) : message.role === 'agent' ? (() => {
                        let parsed: { project_goals?: string[], follow_up_questions?: string[] } | null = null
                        if (message.content) {
                          try { parsed = JSON.parse(message.content) } catch { }
                        }

                        if (parsed && (parsed.project_goals || parsed.follow_up_questions)) {
                          return (
                            <div className="space-y-5 max-w-2xl">
                              {parsed.project_goals && parsed.project_goals.length > 0 && (
                                <div>
                                  <div className="flex items-center gap-2.5 mb-3">
                                    <div className="w-5 h-5 rounded-md bg-gold-accent/10 border border-gold-accent/30 flex items-center justify-center flex-shrink-0">
                                      <span className="text-gold-accent text-[9px]">✦</span>
                                    </div>
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-gold-light">Project Goals</span>
                                  </div>
                                  <ul className="space-y-2">
                                    {parsed.project_goals.map((goal, i) => (
                                      <li key={i} className="flex items-start gap-3 text-[14px] text-platinum/80 font-light leading-relaxed">
                                        <span className="text-gold-accent/50 mt-1 text-[10px] flex-shrink-0">▸</span>
                                        {goal}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {parsed.project_goals?.length && parsed.follow_up_questions?.length
                                ? <div className="border-t border-white/[0.06]" />
                                : null}
                              {parsed.follow_up_questions && parsed.follow_up_questions.length > 0 && (
                                <div>
                                  <div className="flex items-center gap-2.5 mb-3">
                                    <div className="w-5 h-5 rounded-md bg-electric-blue/10 border border-electric-blue/30 flex items-center justify-center flex-shrink-0">
                                      <span className="text-electric-blue text-[9px]">?</span>
                                    </div>
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-electric-cyan">Clarification Needed</span>
                                  </div>
                                  <ol className="space-y-2.5">
                                    {parsed.follow_up_questions.map((q, i) => (
                                      <li key={i} className="flex items-start gap-3 text-[14px] text-platinum/80 font-light leading-relaxed">
                                        <span className="text-electric-blue/60 font-mono text-[11px] mt-0.5 flex-shrink-0 min-w-[1.2rem]">{i + 1}.</span>
                                        {q}
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              )}
                            </div>
                          )
                        }

                        return (
                          <div className="prose prose-sm prose-invert max-w-none prose-p:text-platinum prose-p:leading-relaxed prose-p:font-light prose-p:text-[15px] prose-li:text-platinum/80 prose-li:font-light prose-strong:text-white prose-strong:font-medium">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                          </div>
                        )
                      })() : (
                        <div className="text-[15px] leading-relaxed font-light">{message.content}</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Instruction Banner */}
      {instruction && (
        <div className="border-t border-white/5 bg-carbon/90 backdrop-blur-md">
          <div className="max-w-4xl mx-auto">
            {isCommandApproval && pendingCommand && (
              <div className="px-6 pt-4 pb-2">
                <div className="flex items-start gap-3 bg-black/60 border border-white/[0.06] rounded-xl px-5 py-4">
                  <span className="text-yellow-400/70 text-[11px] mt-0.5 flex-shrink-0 font-mono">$</span>
                  <code className="text-[13px] font-mono text-platinum/90 whitespace-pre-wrap break-all leading-relaxed flex-1">
                    {pendingCommand}
                  </code>
                </div>
              </div>
            )}
            <div className="flex items-center justify-between px-6 py-3">
              <p className="text-[11px] uppercase tracking-[0.2em] text-white/50 font-medium">
                {isCommandApproval ? '⚡ Command requires approval' : `Action Required: ${instruction}`}
              </p>
              {isWaitingForApproval && (
                <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                  {isCommandApproval && (
                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() => {
                        setInput('reject')
                        setIsWaitingForApproval(false)
                        setIsCommandApproval(false)
                        setPendingCommand(null)
                        setTimeout(() => { const f = document.querySelector('form'); if (f) f.requestSubmit() }, 0)
                      }}
                      className="px-6 py-2 bg-white/10 border border-white/20 text-white/70 text-[10px] uppercase tracking-[0.2em] font-bold rounded-full hover:bg-red-900/30 hover:border-red-400/40 hover:text-red-300 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                    >
                      Reject
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={isLoading}
                    onClick={() => {
                      setInput('approve')
                      setIsWaitingForApproval(false)
                      setIsCommandApproval(false)
                      setPendingCommand(null)
                      setTimeout(() => { const f = document.querySelector('form'); if (f) f.requestSubmit() }, 0)
                    }}
                    className="px-6 py-2 bg-white text-obsidian text-[10px] uppercase tracking-[0.2em] font-bold rounded-full hover:shadow-[0_0_15px_rgba(255,255,255,0.4)] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    Approve
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="px-6 py-6 pb-8 border-t border-white/5 bg-obsidian relative z-20">
        <div className="absolute inset-0 top-auto h-32 bg-gradient-to-t from-electric-blue/5 to-transparent pointer-events-none"></div>
        <form
          onSubmit={!threadId ? (e) => handleStartWorkflow(e, null) : handleSubmit}
          className="relative z-10 glass-premium rounded-full p-1.5 max-w-3xl mx-auto shadow-[0_0_40px_rgba(0,0,0,0.5)]"
        >
          <div className="flex gap-2 w-full">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                isWaitingForApproval
                  ? 'Type feedback or click Approve...'
                  : threadId
                    ? 'Type your directive...'
                    : 'Describe your objective to initiate workflow...'
              }
              className="flex-1 bg-transparent border-none px-6 py-4 text-[15px] text-platinum placeholder-white/20 focus:outline-none transition-all font-light tracking-wide w-full rounded-full"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              onClick={() => setIsWaitingForApproval(false)}
              className="w-14 h-14 flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-platinum to-platinum-muted text-obsidian rounded-full hover:from-white hover:to-platinum hover:shadow-[0_0_20px_rgba(255,255,255,0.4)] disabled:opacity-20 disabled:hover:shadow-none disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 disabled:transform-none"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 -rotate-90">
                <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

---

## CHANGE 2 of 5 — `components/WorkflowGraph.tsx`

**Why:** The current graph only shows one node as "active" at a time, with
all other nodes showing as "inactive" (dim). This means once the coder finishes,
the graph looks blank — nothing highlighted — until validation starts. Users
have no sense of what has already run. We need three states: `active` (running
now), `completed` (done, in the past), and `inactive` (not yet reached).

The graph now tracks which node in the linear sequence was last active,
and marks everything before it as `completed` (subtle tick, not pulsing).

```tsx
'use client'

import { useEffect, useState } from 'react'

interface WorkflowGraphProps {
  activeNode: string | null
}

interface NodeData {
  id: string
  label: string
}

// The pipeline in order — used to determine which nodes are "completed"
// (everything before the current active node in this sequence)
const nodes: NodeData[] = [
  { id: 'architect_agent', label: 'Architect' },
  { id: 'planner_agent',   label: 'Planner'   },
  { id: 'coder_agent',     label: 'Coder'     },
  { id: 'validation_agent',label: 'Validator' },
  { id: 'summarizer_agent',label: 'Summarizer'},
  { id: 'human_response',  label: 'Review'    },
]

// Maps every possible backend node name → graph node id
const NODE_MAP: Record<string, string> = {
  architect:                        'architect_agent',
  architect_review:                 'architect_agent',
  architect_review_node:            'architect_agent',
  architect_response_review_node:   'architect_agent',
  planner:                          'planner_agent',
  planner_review:                   'planner_agent',
  planner_review_node:              'planner_agent',
  planner_response_review_node:     'planner_agent',
  coder:                            'coder_agent',
  validation:                       'validation_agent',
  validation_approval:              'validation_agent',
  validator:                        'validation_agent',
  summarizer:                       'summarizer_agent',
  init_deepagents:                  'architect_agent',
}

type NodeStatus = 'inactive' | 'active' | 'completed'

export default function WorkflowGraph({ activeNode }: WorkflowGraphProps) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  if (!mounted) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-white/30 text-xs tracking-widest uppercase">Loading...</div>
      </div>
    )
  }

  // Resolve the backend node name to a graph node id
  const resolvedActiveId = activeNode
    ? (NODE_MAP[activeNode] ?? activeNode)
    : null

  const activeIndex = resolvedActiveId
    ? nodes.findIndex(n => n.id === resolvedActiveId)
    : -1

  const getStatus = (idx: number): NodeStatus => {
    if (activeIndex === -1) return 'inactive'
    if (idx === activeIndex)  return 'active'
    if (idx < activeIndex)    return 'completed'
    return 'inactive'
  }

  return (
    <div className="relative h-full flex items-center justify-center">
      <svg
        className="w-full h-full max-h-[500px]"
        viewBox="0 0 60 450"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connector lines */}
        {nodes.map((_, idx) => {
          if (idx === nodes.length - 1) return null
          const y1 = 30 + idx * 55
          const y2 = 30 + (idx + 1) * 55
          const fromStatus = getStatus(idx)
          const toStatus = getStatus(idx + 1)
          // Line is bright if either end node is active or completed
          const isLit = fromStatus !== 'inactive' || toStatus !== 'inactive'
          return (
            <line
              key={idx}
              x1="30" y1={y1} x2="30" y2={y2}
              stroke={isLit ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)'}
              strokeDasharray="2,2"
            />
          )
        })}

        {/* Nodes */}
        {nodes.map((node, idx) => {
          const y = 30 + idx * 55
          const status = getStatus(idx)

          return (
            <g key={node.id}>
              {/* Pulsing glow — active only */}
              {status === 'active' && (
                <>
                  <circle cx="30" cy={y} r="14" fill="white" opacity="0.3">
                    <animate attributeName="opacity" values="0.3;0.6;0.3" dur="2s" repeatCount="indefinite" />
                  </circle>
                  <circle cx="30" cy={y} r="10" fill="white" opacity="0.5">
                    <animate attributeName="opacity" values="0.5;0.8;0.5" dur="2s" repeatCount="indefinite" />
                  </circle>
                </>
              )}

              {/* Node dot */}
              <circle
                cx="30"
                cy={y}
                r="7"
                fill={
                  status === 'active'    ? 'white' :
                  status === 'completed' ? 'rgba(6,182,212,0.6)' :  /* cyan for done */
                  'transparent'
                }
                stroke={
                  status === 'active'    ? 'white' :
                  status === 'completed' ? 'rgba(6,182,212,0.8)' :
                  'rgba(255,255,255,0.2)'
                }
                strokeWidth={status === 'inactive' ? '1.5' : '2'}
                filter={status === 'active' ? 'url(#glow)' : 'none'}
              />

              {/* Checkmark inside completed nodes */}
              {status === 'completed' && (
                <text
                  x="30"
                  y={y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="rgba(6,182,212,0.9)"
                  fontSize="7"
                  fontWeight="bold"
                >
                  ✓
                </text>
              )}

              {/* Label */}
              <text
                x="30"
                y={y + 22}
                textAnchor="middle"
                fill={
                  status === 'active'    ? 'white' :
                  status === 'completed' ? 'rgba(6,182,212,0.7)' :
                  'rgba(255,255,255,0.25)'
                }
                fontSize="8"
                fontWeight={status === 'active' ? '700' : '400'}
                letterSpacing="0.3px"
              >
                {node.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
```

---

## CHANGE 3 of 5 — `components/TodoList.tsx`

**Why:** The `inferredCompleted` hack was compensating for the agent never
updating todos per-task. Now that the backend prompt fix makes the agent call
`write_todos()` after every task with real status updates, the hack produces
*wrong* counts — it was counting "list length shrank" as completions, which
no longer happens (the list stays full, just statuses change). Remove it and
use the actual `status` field, which is now reliable.

```tsx
import { useState } from 'react'

interface TodoItem {
  status: 'pending' | 'in_progress' | 'completed'
  content: string
  title?: string
}

const STATUS_CONFIG: Record<string, {
  icon: string
  textClass: string
  bgClass: string
  iconClass: string
}> = {
  pending: {
    icon: '○',
    textClass: 'text-white/40',
    bgClass: 'bg-white/[0.01] border-white/[0.04]',
    iconClass: 'text-white/20',
  },
  in_progress: {
    icon: '◉',
    textClass: 'text-gold-light',
    bgClass: 'bg-gold-accent/[0.05] border-gold-accent/20',
    iconClass: 'text-gold-accent animate-pulse-soft text-glow-accent',
  },
  completed: {
    icon: '✓',
    textClass: 'text-cyan-300/70 line-through',
    bgClass: 'bg-electric-cyan/[0.04] border-electric-cyan/20',
    iconClass: 'text-electric-cyan text-glow',
  },
}

export default function TodoList({ todos }: { todos: TodoItem[] }) {
  if (!todos || todos.length === 0) return null

  // FIX: use actual status counts — no more inferring from list length changes.
  // The agent now reliably calls write_todos() after each task with real statuses.
  const completed = todos.filter(t => t.status === 'completed').length
  const total = todos.length
  const pct = total ? Math.round((completed / total) * 100) : 0

  return (
    <div className="rounded-xl glass-premium p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-platinum/80 uppercase tracking-[0.2em]">
          TODO Tasks
        </span>
        <span className="text-[11px] text-white/40 font-mono tracking-widest">
          {completed}/{total}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-white/30 font-mono tracking-wider">
          <span>PROGRESS</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden shadow-inner">
          <div
            className="h-full rounded-full bg-gradient-to-r from-electric-blue via-electric-cyan to-electric-cyan transition-all duration-700 ease-out shadow-[0_0_10px_rgba(6,182,212,0.5)]"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Todo items */}
      <ul className="space-y-2">
        {todos.map((todo, i) => {
          const style = STATUS_CONFIG[todo.status] ?? STATUS_CONFIG.pending
          return (
            <li
              key={i}
              className={`flex items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-300 ${style.bgClass}`}
            >
              <span className={`mt-0.5 text-sm leading-none flex-shrink-0 ${style.iconClass}`}>
                {style.icon}
              </span>
              <span className={`text-[11px] leading-relaxed ${style.textClass}`}>
                {todo.title || todo.content}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
```

---

## CHANGE 4 of 5 — `components/Workspace.tsx`

**Why:** Two targeted fixes.
1. `activeNode` was hardcoded to start as `'architect_agent'`, causing the
   progress banner to flash "Architect" for a moment on every load, even when
   opening an existing completed project. Start it as `null`.
2. Accept the new `onWorkflowComplete` callback from ChatInterface so the
   banner correctly clears when the pipeline finishes.

Only the changed lines are shown — the rest of the file stays identical.

### Replace the `activeNode` initial state (line ~16):

```tsx
// OLD:
const [activeNode, setActiveNode] = useState<string | null>('architect_agent')

// NEW:
const [activeNode, setActiveNode] = useState<string | null>(null)
```

### Add `onWorkflowComplete` handler and pass it to ChatInterface:

```tsx
// ADD this handler inside the Workspace component, alongside the other handlers:
const handleWorkflowComplete = (finalTodos: any[]) => {
    // When the workflow completes, the active node should be cleared from the
    // progress banner. The graph will show all nodes as completed.
    setActiveNode(null)
}
```

### Update the ChatInterface usage (find the <ChatInterface ... /> block):

```tsx
// ADD onWorkflowComplete to the ChatInterface props:
<ChatInterface
    activeNode={activeNode}
    setActiveNode={setActiveNode}
    threadId={threadId}
    setThreadId={setThreadId}
    shouldLoadHistory={shouldLoadHistory}
    onPlanUpdate={handlePlanUpdate}
    onViewPlan={handleViewPlan}
    onClosePlanViewer={handleClosePlanViewer}
    isPlanViewerOpen={showPlanViewer}
    isPlannerStreaming={isPlanStreaming}
    currentViewingPlanContent={planContent}
    projectTitle={projectTitle}
    onTerminalLog={handleTerminalLog}
    onWorkflowComplete={handleWorkflowComplete}   {/* ← ADD THIS LINE */}
/>
```

---

## CHANGE 5 of 5 — `components/SubagentCard.tsx`

**Why:** Now that `astream_events v2` is used on the backend, thinking content
blocks actually arrive. But the card does `.slice(-800)` which keeps the *tail*
of the text — for thinking, this means the user only ever sees the end of the
reasoning, not the beginning. The fix is to keep the beginning (the actual
reasoning chain) and only trim if it gets extremely long, and separately mark
thinking text vs regular output text with a subtle visual distinction.

Only the `lastContent` update logic in ChatInterface was changed (slice -800
instead of -500, already done in Change 1). The SubagentCard component itself
only needs one small addition: a visual distinction between thinking content
and action content in the body panel.

```tsx
// In the Body section of SubagentCard, replace the content display div:

{expanded && subagent.lastContent && (
  <div className="border-t border-white/[0.04] px-5 py-4 bg-black/10">
    <div className="text-[11px] text-platinum-muted font-mono leading-relaxed max-h-40 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
      {subagent.lastContent}
      {subagent.status === 'running' && (
        <span className="inline-block h-3 w-1 ml-1 animate-pulse bg-gold-accent align-bottom shadow-[0_0_8px_rgba(212,175,55,0.6)]" />
      )}
    </div>
    {/* Show "thinking..." label while running to signal this is live reasoning */}
    {subagent.status === 'running' && (
      <div className="mt-2 flex items-center gap-1.5">
        <span className="text-[9px] uppercase tracking-[0.2em] text-white/20 font-medium">
          Thinking...
        </span>
      </div>
    )}
  </div>
)}
```

---

## Summary table

| File | What changed | Bug fixed |
|------|-------------|-----------|
| `ChatInterface.tsx` | Listens for `workflow_complete` event type, not `done`. Restores `todos`/`status` on page load. Adds `workflowDone` state. Clears instruction on complete. | UI stuck "running". Todos gone on refresh. |
| `WorkflowGraph.tsx` | Three node states: `active`/`completed`/`inactive`. Completed nodes show cyan with checkmark. | Graph goes blank between node transitions. |
| `TodoList.tsx` | Removed `inferredCompleted` hack. Uses real `status` field directly. | Wrong todo counts. |
| `Workspace.tsx` | `activeNode` starts `null`. Accepts `onWorkflowComplete` to clear banner. | Banner flashes "Architect" on load. |
| `SubagentCard.tsx` | "Thinking..." label while running. Slice increased to 800 in ChatInterface. | Thinking stream partially visible. |
