'use client'

import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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

interface CommentaryLine {
  kind: 'token' | 'tool_start' | 'tool_end'
  text: string
}

interface Message {
  role: 'user' | 'agent'
  content: string
  node?: string
  isLoading?: boolean
  planContent?: string  // Stores the actual plan content for planner messages
  commentary?: CommentaryLine[]  // Live agent commentary (coder/validation/tester)
  commentaryNode?: string        // Which agent produced this commentary
  isCommentaryLive?: boolean     // Still streaming
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
  const [isWorkflowInitialized, setIsWorkflowInitialized] = useState(false)
  const [isWaitingForApproval, setIsWaitingForApproval] = useState(false)
  const [isCommandApproval, setIsCommandApproval] = useState(false) // true when approve/reject is for a command
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
    // Commentary state for coder/validation/tester agents
    let commentaryBuffer: CommentaryLine[] = []
    let commentaryNode = ''
    let commentaryMsgIdx = -1  // index of the commentary placeholder message

    if (!reader) throw new Error('No reader available')

    // Update the loading message to streaming message
    setMessages((prev) => {
      const newMessages = [...prev]
      const lastMsgIdx = newMessages.length - 1
      if (lastMsgIdx >= 0) {
        console.log('Starting stream, updating placeholder at index:', lastMsgIdx)
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

          // Handle streaming tokens (from planner) or complete response (from architect)
          if (data.token) {
            const tokenStr = extractText(data.token)
            // For interrupt responses (architect), replace the message
            if (data.is_interrupt) {
              currentAgentMessage = tokenStr

              // Update node if provided
              if (data.agent_node) {
                currentNode = data.agent_node
                setActiveNode(data.agent_node)
              }

              // Update instruction if provided
              if (data.instruction) {
                setInstruction(data.instruction)
              }

              // Track if this is an approval-type interrupt
              setIsWaitingForApproval(true)
              // Detect if it's a command approval (tester or validation)
              setIsCommandApproval(data.interrupt_type === 'command_approval')

              // Update message content for architect (non-planner) responses
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
              // This is streaming from planner - only update plan viewer, NOT chat
              currentAgentMessage += tokenStr
              if (!isPlannerStreaming) {
                isPlannerStreaming = true
                // Update node to planner and keep message in loading state
                setMessages((prev) => {
                  const newMessages = [...prev]
                  const lastMsgIdx = newMessages.length - 1
                  if (lastMsgIdx >= 0) {
                    newMessages[lastMsgIdx] = {
                      ...newMessages[lastMsgIdx],
                      node: 'planner',
                      isLoading: true, // Keep loading state
                    }
                  }
                  return newMessages
                })
              }
              // Update plan content in real-time (only in plan viewer)
              if (onPlanUpdate) {
                onPlanUpdate(currentAgentMessage, true)
              }
            }

            // Update node if provided
            if (data.agent_node) {
              currentNode = data.agent_node
              setActiveNode(data.agent_node)
            }
          } else if (data.progress) {
            // Node transition event - update active node and show status
            currentNode = data.progress
            setActiveNode(data.progress)

            const nodeLabels: Record<string, string> = {
              'init_deepagents': '🔧 Initializing agents...',
              'coder_agent': '💻 Coder is building...',
              'validation_agent': '✅ Validator is checking...',
              'summarizer_agent': '📋 Summarizer is compiling results...',
              'human_response': '👤 Waiting for your review...',
            }
            const statusText = nodeLabels[data.progress] || `Running ${data.progress}...`

            if (data.status === 'running') {
              setMessages((prev) => {
                const newMessages = [...prev]
                const lastMsgIdx = newMessages.length - 1
                if (lastMsgIdx >= 0 && newMessages[lastMsgIdx].isLoading) {
                  newMessages[lastMsgIdx] = {
                    ...newMessages[lastMsgIdx],
                    content: statusText,
                    node: data.progress,
                    isLoading: true,
                  }
                }
                return newMessages
              })
            }
          } else if (data.type === 'agent_token') {
            // Live LLM token from coder/validation/tester → commentary block in chat
            const tokenStr = extractText(data.content)
            if (!tokenStr) continue // Skip empty tokens

            const line: CommentaryLine = { kind: 'token', text: tokenStr }
            commentaryBuffer.push(line)
            if (commentaryNode !== data.node) {
              commentaryNode = data.node
            }
            // Create or update the commentary placeholder message
            setMessages((prev) => {
              const newMessages = [...prev]
              if (commentaryMsgIdx === -1 || commentaryMsgIdx >= newMessages.length) {
                // Insert a new commentary bubble before the loading placeholder
                const insertAt = newMessages.length - 1
                newMessages.splice(insertAt, 0, {
                  role: 'agent',
                  content: '',
                  node: data.node,
                  isLoading: false,
                  commentary: [...commentaryBuffer],
                  commentaryNode: data.node,
                  isCommentaryLive: true,
                })
                commentaryMsgIdx = insertAt
              } else {
                newMessages[commentaryMsgIdx] = {
                  ...newMessages[commentaryMsgIdx],
                  commentary: [...commentaryBuffer],
                  commentaryNode: data.node,
                  isCommentaryLive: true,
                }
              }
              return newMessages
            })
            continue

          } else if (data.type === 'agent_tool_start') {
            // Tool call start → append to commentary
            const toolName = data.tool || ''
            const argsStr = data.args ? Object.entries(data.args).map(([k, v]) => `${k}=${v}`).join(', ') : ''
            const line: CommentaryLine = { kind: 'tool_start', text: `${toolName}  ${argsStr}` }
            commentaryBuffer.push(line)
            setMessages((prev) => {
              const newMessages = [...prev]
              if (commentaryMsgIdx >= 0 && commentaryMsgIdx < newMessages.length) {
                newMessages[commentaryMsgIdx] = {
                  ...newMessages[commentaryMsgIdx],
                  commentary: [...commentaryBuffer],
                }
              }
              return newMessages
            })
            continue

          } else if (data.type === 'agent_tool_end') {
            // Tool call end → append to commentary
            const toolName = data.tool || ''
            const outStr = data.output || ''
            const line: CommentaryLine = { kind: 'tool_end', text: `${toolName}  ${outStr}` }
            commentaryBuffer.push(line)
            setMessages((prev) => {
              const newMessages = [...prev]
              if (commentaryMsgIdx >= 0 && commentaryMsgIdx < newMessages.length) {
                newMessages[commentaryMsgIdx] = {
                  ...newMessages[commentaryMsgIdx],
                  commentary: [...commentaryBuffer],
                }
              }
              return newMessages
            })
            continue

          } else if (data.terminal_log) {
            // Handle terminal log events from execute_command tool
            if (onTerminalLog) {
              onTerminalLog(data.terminal_log)
            }
            continue
          } else if (data.done) {
            // Stream completed - update active node
            if (data.agent_node) {
              setActiveNode(data.agent_node)
              currentNode = data.agent_node
            }
          } else if (data.error) {
            throw new Error(data.error)
          }
        } catch (e) {
          // Invalid JSON, skip
          console.log('Failed to parse line:', line)
        }
      }
    }

    setIsLoading(false)

    // Notify that streaming is complete
    if (isPlannerStreaming && onPlanUpdate) {
      onPlanUpdate(currentAgentMessage, false)
    }

    // Finalize message state
    setMessages((prev) => {
      const newMessages = [...prev]
      // Mark commentary message as no longer live
      if (commentaryMsgIdx >= 0 && commentaryMsgIdx < newMessages.length) {
        newMessages[commentaryMsgIdx] = {
          ...newMessages[commentaryMsgIdx],
          isCommentaryLive: false,
        }
      }
      const lastMsgIdx = newMessages.length - 1
      if (lastMsgIdx >= 0) {
        if (isPlannerStreaming) {
          // For planner: store the actual plan content in planContent field
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            content: 'Plan generated',
            planContent: currentAgentMessage,
            node: 'planner',
            isLoading: false,
          }
        } else if (newMessages[lastMsgIdx].isLoading || !newMessages[lastMsgIdx].content) {
          // For other agents: set actual content
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
                {/* Commentary block for coder/validation/tester agents */}
                {message.commentary && message.commentary.length > 0 ? (
                  <div className="w-full max-w-[95%] rounded border border-white/10 bg-[#000000] shadow-2xl">
                    {/* Commentary header */}
                    <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/5">
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] uppercase font-mono tracking-[0.2em] font-medium" style={{
                          color: message.commentaryNode?.includes('coder') ? '#e5e5e5' :
                            message.commentaryNode?.includes('validation') ? '#a3a3a3' :
                              message.commentaryNode?.includes('summarizer') ? '#d4af37' : '#ffffff'
                        }}>
                          {message.commentaryNode || 'agent'}
                        </span>
                        {message.isCommentaryLive && (
                          <span className="flex items-center gap-1.5 ml-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-platinum animate-pulse" />
                            <span className="text-[8px] font-mono text-platinum/50 uppercase tracking-[0.3em]">processing</span>
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Commentary lines */}
                    <div className="px-5 py-4 font-mono text-[10px] leading-relaxed space-y-1 max-h-72 overflow-y-auto custom-scrollbar">
                      {message.commentary.map((line, lineIdx) => {
                        if (line.kind === 'tool_start') {
                          return (
                            <div key={lineIdx} className="flex items-start gap-3 text-white/50">
                              <span className="mt-px flex-shrink-0 text-[8px] opacity-50">❯</span>
                              <span className="break-all">{line.text}</span>
                            </div>
                          )
                        } else if (line.kind === 'tool_end') {
                          return (
                            <div key={lineIdx} className="flex items-start gap-3 text-white/40">
                              <span className="mt-px flex-shrink-0 text-[8px] opacity-50">#</span>
                              <span className="break-all">{line.text}</span>
                            </div>
                          )
                        } else {
                          // token — just render inline as prose
                          return (
                            <span key={lineIdx} className="text-white/80 whitespace-pre-wrap">{line.text}</span>
                          )
                        }
                      })}
                    </div>
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
                      className={`max-w-[75%] ${message.role === 'user'
                        ? 'bg-white/5 text-platinum border border-white/5 rounded-2xl rounded-tr-sm px-5 py-4'
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
                        ) : message.role === 'agent' ? (
                          <div className="prose prose-sm prose-invert max-w-none prose-p:text-platinum prose-p:leading-relaxed prose-p:font-light prose-p:text-[15px] prose-li:text-platinum/80 prose-li:font-light prose-strong:text-white prose-strong:font-medium">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {message.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
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
        <div className="px-6 py-4 border-t border-white/5 bg-carbon/80 backdrop-blur-md">
          <div className="flex items-center justify-between max-w-4xl mx-auto">
            <p className="text-[11px] uppercase tracking-[0.2em] text-white/60 font-medium">
              {isCommandApproval ? '⚡ Command Pending:' : 'Action Required:'} {instruction}
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
      )}

      {/* Input Area */}
      <div className="px-6 py-6 pb-8 border-t border-white/5 bg-obsidian relative">
        {/* Subtle glow behind input */}
        <div className="absolute inset-0 top-auto h-24 bg-gradient-to-t from-white/5 to-transparent pointer-events-none"></div>
        <form onSubmit={!threadId ? (e) => handleStartWorkflow(e, null) : handleSubmit} className="relative z-10">
          <div className="flex gap-3 max-w-3xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                isWaitingForApproval
                  ? 'Type feedback or click Approve...'
                  : threadId
                    ? 'Type your response...'
                    : 'Describe your objective to initiate workflow...'
              }
              className="flex-1 bg-white/[0.03] border border-white/10 rounded-full px-6 py-4 text-[14px] text-platinum placeholder-white/20 focus:outline-none focus:border-white/30 focus:bg-white/[0.05] transition-all font-light tracking-wide shadow-inner dropdown"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              onClick={() => setIsWaitingForApproval(false)}
              className="w-14 h-14 flex items-center justify-center bg-platinum text-obsidian rounded-full hover:bg-white hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] disabled:opacity-20 disabled:hover:shadow-none disabled:cursor-not-allowed transition-all"
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
