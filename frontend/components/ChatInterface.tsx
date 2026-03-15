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
  // Deep agent activity block (replaces old commentary)
  isDeepAgentBlock?: boolean
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Helper to safely extract string from potentially object-based LLM tokens
const extractText = (content: any): string => {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content.map(c => extractText(c)).join('')
  }
  if (typeof content === 'object' && content !== null) {
    return content.text || JSON.stringify(content)
  }
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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Restore state from localStorage and backend
  useEffect(() => {

    // Function to perform the restoration for a given ID
    const restoreSession = async (idToRestore: string) => {
      console.log('Restoring session for thread_id:', idToRestore)
      setIsLoading(true)
      try {
        const response = await fetch(`${API_BASE_URL}/workflow/state/${idToRestore}`)

        if (!response.ok) {
          console.log('Failed to restore session, clearing storage')
          // Only clear local storage if we were relying on it (no prop provided)
          if (!threadId) {
            localStorage.removeItem('thread_id')
          }
          return
        }

        const data = await response.json()
        console.log('Restored state:', data)

        if (data.thread_id) {
          // If we didn't have a threadId, set it now. 
          // If we did, valid check to ensure it matches?
          if (!threadId) setThreadId(data.thread_id)

          if (data.active_node) setActiveNode(data.active_node)
          if (data.instruction) setInstruction(data.instruction)

          if (data.messages && Array.isArray(data.messages)) {
            setMessages(data.messages.map((msg: any) => {
              // Special handling for planner messages to enable View Plan button
              if (msg.node?.includes('planner') && msg.role === 'agent') {
                return {
                  role: msg.role,
                  content: 'Plan generated', // Display text for card
                  planContent: msg.content, // Actual content for viewer
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
        setIsWorkflowInitialized(true) // Mark as initialized so next message goes to /chat, not /start
      }
    }

    // Case 1: Explicit instruction to load history for active thread
    if (threadId && shouldLoadHistory) {
      restoreSession(threadId)
      return
    }

    // Case 2: Auto-restore from localStorage if no threadId provided (legacy/standalone mode)
    const savedThreadId = localStorage.getItem('thread_id')
    if (savedThreadId && !threadId) {
      console.log('Found saved thread_id in storage:', savedThreadId)
      restoreSession(savedThreadId)
    }
  }, [threadId, setThreadId, setActiveNode, shouldLoadHistory])

  // Save threadId to localStorage when it changes
  useEffect(() => {
    if (threadId) {
      localStorage.setItem('thread_id', threadId)
    }
  }, [threadId])

  const handleStartWorkflow = async (e: React.FormEvent, existingThreadId: string | null = null) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)
    setActiveNode('architect_agent')

    // Show user message and loading indicator immediately
    setMessages([
      { role: 'user', content: userMessage },
      { role: 'agent', content: '', node: 'architect_agent', isLoading: true }, // Set node to architect_agent
    ])

    try {
      const response = await fetch(`${API_BASE_URL}/workflow/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          initial_query: userMessage,
          thread_id: existingThreadId,
          title: projectTitle || ""
        }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Server error:', response.status, errorText)
        throw new Error(`Server error: ${response.status}`)
      }

      const data = await response.json()
      console.log('Backend response:', data)

      setThreadId(data.thread_id)
      setActiveNode(data.agent_node || 'architect')
      setInstruction(data.agent_instruction || null)
      setIsWaitingForApproval(true)
      setIsWorkflowInitialized(true)

      // Update with actual response
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
        {
          role: 'agent',
          content: 'Error starting workflow. Please try again.',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading || !threadId) return

    // If we have a threadId but workflow not initialized, run start logic
    if (!isWorkflowInitialized && threadId) {
      return handleStartWorkflow(e, threadId)
    }

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    // Add user message and loading placeholder
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage },
      { role: 'agent', content: '', node: 'agent', isLoading: true },
    ])

    try {
      // Always use /workflow/chat for all subsequent interactions
      await handleStreamingResponse(userMessage, `${API_BASE_URL}/workflow/chat`)
    } catch (error) {
      console.error('Error processing message:', error)
      setMessages((prev) => {
        const newMessages = [...prev]
        const lastMsgIdx = newMessages.length - 1
        if (lastMsgIdx >= 0) {
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            content: 'Error getting response. Please try again.',
            isLoading: false
          }
        }
        return newMessages
      })
      setIsLoading(false)
    }
  }

  const handleStreamingResponse = async (userMessage: string, endpoint: string) => {
    abortControllerRef.current = new AbortController()

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        run_id: threadId,
        query: userMessage,
      }),
      signal: abortControllerRef.current.signal,
    })

    if (!response.ok) {
      throw new Error('Streaming failed')
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentAgentMessage = ''
    let currentNode = activeNode || 'agent'
    let isPlannerStreaming = false
    let deepAgentBlockInserted = false

    if (!reader) throw new Error('No reader available')

    // Update the loading message to streaming message
    setMessages((prev) => {
      const newMessages = [...prev]
      const lastMsgIdx = newMessages.length - 1
      if (lastMsgIdx >= 0) {
        newMessages[lastMsgIdx] = {
          ...newMessages[lastMsgIdx],
          role: 'agent',
          content: '',
          node: currentNode,
        }
      }
      return newMessages
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

          // Handle progress events — update active node in graph
          if (data.progress) {
            currentNode = data.progress
            setActiveNode(data.progress)
            continue
          }

          // ── Subagent lifecycle events ──────────────────────────
          if (data.type === 'subagent_start') {
            // On first subagent, REPLACE the loading placeholder with the deep agent block
            // (instead of inserting before it, which leaves a stale planner card)
            if (!deepAgentBlockInserted) {
              deepAgentBlockInserted = true
              setMessages((prev) => {
                const newMessages = [...prev]
                const lastIdx = newMessages.length - 1
                // Replace the loading placeholder with the deep agent block
                newMessages[lastIdx] = {
                  role: 'agent',
                  content: '',
                  node: data.node,
                  isLoading: false,
                  isDeepAgentBlock: true,
                }
                return newMessages
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

          // ── Todo updates ───────────────────────────────────────
          if (data.type === 'todo_update') {
            setTodos(data.todos || [])
            continue
          }

          // ── Agent tokens → update subagent lastContent ────────
          if (data.type === 'agent_token') {
            const tokenStr = extractText(data.content)
            if (!tokenStr) continue
            setSubagents((prev) => {
              const next = new Map(prev)
              const existing = next.get(data.node)
              if (existing) {
                // Keep last ~500 chars to avoid memory bloat
                const updated = (existing.lastContent + tokenStr).slice(-500)
                next.set(data.node, { ...existing, lastContent: updated })
              }
              return next
            })
            continue
          }

          // ── Tool events (shown in subagent card) ──────────────
          if (data.type === 'agent_tool_start' || data.type === 'agent_tool_end') {
            // Update subagent lastContent with tool info
            const toolText = data.type === 'agent_tool_start'
              ? `\n❯ ${data.tool}...`
              : `\n✓ ${data.tool} done`
            setSubagents((prev) => {
              const next = new Map(prev)
              const existing = next.get(data.node)
              if (existing) {
                const updated = (existing.lastContent + toolText).slice(-500)
                next.set(data.node, { ...existing, lastContent: updated })
              }
              return next
            })
            continue
          }

          // Handle streaming tokens (from planner) or complete response (from architect)
          if (data.token) {
            const tokenStr = extractText(data.token)
            if (data.is_interrupt) {
              currentAgentMessage = tokenStr

              if (data.agent_node) {
                currentNode = data.agent_node
                setActiveNode(data.agent_node)
              }
              if (data.instruction) {
                setInstruction(data.instruction)
              }
              // Capture the actual pending command for command_approval so user can see it
              if (data.interrupt_type === 'command_approval') {
                setPendingCommand(tokenStr)
              }

              setIsWaitingForApproval(true)
              setIsCommandApproval(data.interrupt_type === 'command_approval')

              setMessages((prev) => {
                const newMessages = [...prev]
                const lastMsgIdx = newMessages.length - 1
                if (lastMsgIdx >= 0) {
                  newMessages[lastMsgIdx] = {
                    ...newMessages[lastMsgIdx],
                    content: currentAgentMessage,
                    node: currentNode,
                    isLoading: false,
                  }
                }
                return newMessages
              })
            } else {
              // Planner streaming — update plan viewer only
              currentAgentMessage += tokenStr
              if (!isPlannerStreaming) {
                isPlannerStreaming = true
                setMessages((prev) => {
                  const newMessages = [...prev]
                  const lastMsgIdx = newMessages.length - 1
                  if (lastMsgIdx >= 0) {
                    newMessages[lastMsgIdx] = {
                      ...newMessages[lastMsgIdx],
                      node: 'planner',
                      isLoading: true,
                    }
                  }
                  return newMessages
                })
              }
              if (onPlanUpdate) {
                onPlanUpdate(currentAgentMessage, true)
              }
            }

            if (data.agent_node) {
              currentNode = data.agent_node
              setActiveNode(data.agent_node)
            }
          } else if (data.terminal_log) {
            if (onTerminalLog) {
              onTerminalLog(data.terminal_log)
            }
            continue
          } else if (data.done) {
            if (data.agent_node) {
              setActiveNode(data.agent_node)
              currentNode = data.agent_node
            }
          } else if (data.error) {
            throw new Error(data.error)
          }
        } catch (e) {
          console.log('Failed to parse line:', line)
        }
      }
    }

    setIsLoading(false)

    if (isPlannerStreaming && onPlanUpdate) {
      onPlanUpdate(currentAgentMessage, false)
    }

    // Finalize message state
    setMessages((prev) => {
      const newMessages = [...prev]
      const lastMsgIdx = newMessages.length - 1
      if (lastMsgIdx >= 0) {
        if (isPlannerStreaming) {
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            content: 'Plan generated',
            planContent: currentAgentMessage,
            node: 'planner',
            isLoading: false,
          }
        } else if (newMessages[lastMsgIdx].isLoading || !newMessages[lastMsgIdx].content) {
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            content: currentAgentMessage || 'No response from agent.',
            node: currentNode,
            isLoading: false,
          }
        }
      }
      return newMessages
    })
  }

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
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
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
              >
                {/* Deep agent activity block — SubagentCards + TodoList */}
                {message.isDeepAgentBlock ? (
                  <div className="w-full max-w-[95%] space-y-3">
                    {/* Subagent cards */}
                    {Array.from(subagents.values()).length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between px-1">
                          <span className="text-[9px] font-medium text-white/30 uppercase tracking-[0.2em]">
                            Specialist Agents &middot; {Array.from(subagents.values()).filter(s => s.status === 'complete').length}/{subagents.size} completed
                          </span>
                        </div>
                        {/* Overall progress bar */}
                        <div className="w-full h-1 rounded-full bg-white/[0.04] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-emerald-500/60 to-emerald-400/80 transition-all duration-500"
                            style={{ width: `${subagents.size ? (Array.from(subagents.values()).filter(s => s.status === 'complete').length / subagents.size) * 100 : 0}%` }}
                          />
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                          {Array.from(subagents.values()).map((sa) => (
                            <SubagentCard key={sa.id} subagent={sa} />
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Todo list */}
                    {todos.length > 0 && <TodoList todos={todos} />}
                  </div>
                ) : /* Planner message - Compact card view */
                  message.node?.includes('planner') && message.role === 'agent' ? (
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
                              ) : (
                                <div className="w-1 h-1 rounded-full bg-white/50" />
                              )}
                            </div>
                            <p className="text-[10px] text-white/30 uppercase tracking-widest mt-1">
                              {message.isLoading
                                ? 'Synthesizing...'
                                : 'Finalized'}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            // Check if this message's plan is currently being viewed
                            const isViewingThisPlan = isPlanViewerOpen && currentViewingPlanContent === message.planContent
                            if (isViewingThisPlan) {
                              // Close the viewer
                              onClosePlanViewer?.()
                            } else {
                              // Open viewer with this message's plan content
                              onViewPlan?.(message.planContent || '')
                            }
                          }}
                          disabled={!message.planContent}
                          className={`flex items-center gap-2 px-5 py-2.5 text-[10px] uppercase tracking-[0.2em] font-medium transition-all ${!message.planContent
                            ? 'text-white/20 cursor-not-allowed'
                            : isPlanViewerOpen && currentViewingPlanContent === message.planContent
                              ? 'bg-white text-obsidian rounded-full shadow-[0_0_15px_rgba(255,255,255,0.4)]'
                              : 'bg-white/5 border border-white/10 hover:bg-white/10 text-platinum rounded-full'
                            }`}
                        >
                          {isPlanViewerOpen && currentViewingPlanContent === message.planContent ? (
                            <>
                              Hide
                            </>
                          ) : (
                            <>
                              Inspect
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Regular message display for user and architect */
                    <div
                      className={`max-w-[85%] ${message.role === 'user'
                        ? 'bg-gradient-to-br from-white/10 to-white/5 text-platinum border border-white/10 rounded-2xl rounded-tr-sm px-6 py-4 shadow-[0_8px_30px_rgb(0,0,0,0.12)]'
                        : 'bg-transparent text-platinum border-transparent pl-2 py-4'
                        }`}
                    >
                      {/* Architect badge */}
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
                          // Try to parse architect JSON response
                          let parsed: { project_goals?: string[], follow_up_questions?: string[] } | null = null
                          if (message.content) {
                            try { parsed = JSON.parse(message.content) } catch { /* not JSON */ }
                          }

                          if (parsed && (parsed.project_goals || parsed.follow_up_questions)) {
                            return (
                              <div className="space-y-5 max-w-2xl">
                                {/* Project Goals */}
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
                                {/* Divider */}
                                {parsed.project_goals?.length && parsed.follow_up_questions?.length ? (
                                  <div className="border-t border-white/[0.06]" />
                                ) : null}
                                {/* Follow-up Questions */}
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

                          // Fallback: regular markdown
                          return (
                            <div className="prose prose-sm prose-invert max-w-none prose-p:text-platinum prose-p:leading-relaxed prose-p:font-light prose-p:text-[15px] prose-li:text-platinum/80 prose-li:font-light prose-strong:text-white prose-strong:font-medium">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {message.content}
                              </ReactMarkdown>
                            </div>
                          )
                        })() : (
                          <div className="text-[15px] leading-relaxed font-light">
                            {message.content}
                          </div>
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
            {/* Command display — shown only for command_approval */}
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
                {isCommandApproval ? '⚡ Command requires approval' : 'Action Required:'} {!isCommandApproval && instruction}
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
                      setTimeout(() => {
                        const form = document.querySelector('form')
                        if (form) form.requestSubmit()
                      }, 0)
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
                    setTimeout(() => {
                      const form = document.querySelector('form')
                      if (form) form.requestSubmit()
                    }, 0)
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
        {/* Subtle glow behind input */}
        <div className="absolute inset-0 top-auto h-32 bg-gradient-to-t from-electric-blue/5 to-transparent pointer-events-none"></div>
        <form onSubmit={!threadId ? (e) => handleStartWorkflow(e, null) : handleSubmit} className="relative z-10 glass-premium rounded-full p-1.5 max-w-3xl mx-auto shadow-[0_0_40px_rgba(0,0,0,0.5)]">
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
