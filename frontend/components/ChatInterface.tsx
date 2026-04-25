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
    // Reset textarea height after submission
    const textarea = document.querySelector('textarea')
    if (textarea) textarea.style.height = 'auto'

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
    // Reset textarea height after submission
    const textarea = document.querySelector('textarea')
    if (textarea) textarea.style.height = 'auto'

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
                // Keep all streamed tokens so user can read full reasoning
                const updated = existing.lastContent + tokenStr
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
                const updated = existing.lastContent + toolText
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
          <div className="h-full flex flex-col items-center justify-center animate-fade-in-up">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-charcoal-elevated to-charcoal-base border border-border-subtle flex items-center justify-center mb-6 shadow-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-accent-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
            <h2 className="text-xl font-heading font-medium text-text-primary mb-2">Build with Tarantula</h2>
            <p className="text-sm font-sans text-text-tertiary">Describe your objective to initiate autonomous generation.</p>
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
                      ? 'bg-charcoal-elevated text-text-primary border border-border-subtle rounded-2xl rounded-tr-sm px-6 py-4 shadow-lg'
                      : 'bg-transparent text-text-primary border-transparent pl-2 py-4'
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
                                    <div className="w-6 h-6 rounded bg-accent-indigo/10 border border-accent-indigo/30 flex items-center justify-center flex-shrink-0">
                                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 text-accent-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      </svg>
                                    </div>
                                    <span className="text-[12px] font-heading font-medium text-text-secondary">Project Goals</span>
                                  </div>
                                  <ul className="space-y-2 mb-2">
                                    {parsed.project_goals.map((goal, i) => (
                                      <li key={i} className="flex items-start gap-3 text-[14px] text-text-secondary leading-relaxed">
                                        <div className="w-1.5 h-1.5 rounded-full bg-text-tertiary mt-2 flex-shrink-0"></div>
                                        {goal}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {parsed.project_goals?.length && parsed.follow_up_questions?.length
                                ? <div className="border-t border-border-subtle my-2" />
                                : null}
                              {parsed.follow_up_questions && parsed.follow_up_questions.length > 0 && (
                                <div>
                                  <div className="flex items-center gap-2.5 mb-3">
                                    <div className="w-6 h-6 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center flex-shrink-0">
                                      <span className="text-amber-500 text-sm font-bold">?</span>
                                    </div>
                                    <span className="text-[12px] font-heading font-medium text-text-secondary">Clarification Needed</span>
                                  </div>
                                  <ol className="space-y-3">
                                    {parsed.follow_up_questions.map((q, i) => (
                                      <li key={i} className="flex items-start gap-3 text-[14px] text-text-secondary leading-relaxed">
                                        <span className="text-text-tertiary font-mono text-[11px] mt-0.5 flex-shrink-0 min-w-[1.2rem]">{i + 1}.</span>
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
                          <div className="markdown-content">
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
        <div className="border-t border-border-subtle surface-panel backdrop-blur-md">
          <div className="max-w-4xl mx-auto">
            {isCommandApproval && pendingCommand && (
              <div className="px-6 pt-4 pb-2">
                <div className="flex items-start gap-3 bg-pure-black border border-border-subtle rounded-lg px-5 py-4">
                  <span className="text-accent-indigo text-[12px] mt-0.5 flex-shrink-0 font-mono">$</span>
                  <code className="text-[13px] font-mono text-text-primary whitespace-pre-wrap break-all leading-relaxed flex-1">
                    {pendingCommand}
                  </code>
                </div>
              </div>
            )}
            <div className="flex items-center justify-between px-6 py-4">
              <p className="text-xs font-medium text-text-secondary">
                {isCommandApproval ? '⚡ Command requires approval before execution' : `Action Required: ${instruction}`}
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
                      className="px-5 py-2 bg-transparent hover:bg-white/5 border border-border-subtle text-text-secondary text-xs font-medium rounded-lg disabled:opacity-50 transition-all"
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
                    className="px-5 py-2 bg-text-primary text-pure-black text-xs font-medium rounded-lg hover:bg-white/90 disabled:opacity-50 transition-all"
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
      <div className="px-6 py-4 pb-6 border-t border-border-subtle bg-charcoal-base z-20">
        <form
          onSubmit={!threadId ? (e) => handleStartWorkflow(e, null) : handleSubmit}
          className="relative max-w-4xl mx-auto flex items-end gap-2 bg-charcoal-surface border border-border-subtle rounded-2xl shadow-sm focus-within:border-border-focus focus-within:shadow-md transition-all"
        >
          <div className="flex-1 overflow-hidden">
            <textarea
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(e.target.scrollHeight, 256)}px`
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (input.trim() && !isLoading) {
                    const f = e.currentTarget.closest('form');
                    if (f) f.requestSubmit();
                  }
                }
              }}
              placeholder={
                isWaitingForApproval
                  ? 'Type feedback or click Approve...'
                  : threadId
                    ? 'Message Tarantula...'
                    : 'Describe your objective to initiate workflow...'
              }
              rows={1}
              style={{ minHeight: '52px' }}
              className="w-full bg-transparent border-none px-6 py-4 max-h-64 text-[15px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-0 custom-scrollbar resize-none leading-relaxed"
              disabled={isLoading}
            />
          </div>
          <div className="p-2 flex-shrink-0">
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              onClick={() => setIsWaitingForApproval(false)}
              className="w-10 h-10 flex items-center justify-center bg-white/5 text-text-secondary rounded-xl hover:bg-white/10 hover:text-text-primary border border-border-subtle disabled:opacity-30 disabled:hover:bg-white/5 disabled:hover:text-text-secondary transition-all"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
              </svg>
            </button>
          </div>
        </form>
        <div className="text-center mt-3">
          <p className="text-[11px] text-text-tertiary">Tarantula can make mistakes. Verify critical code generation.</p>
        </div>
      </div>
    </div>
  )
}
