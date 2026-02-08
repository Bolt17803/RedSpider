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
}

interface Message {
  role: 'user' | 'agent'
  content: string
  node?: string
  isLoading?: boolean
  planContent?: string  // Stores the actual plan content for planner messages
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [instruction, setInstruction] = useState<string | null>(null)
  const [isWorkflowInitialized, setIsWorkflowInitialized] = useState(false)
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
      { role: 'agent', content: '', node: activeNode || 'agent', isLoading: true },
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

          // Handle streaming tokens (from planner) or complete response (from architect)
          if (data.token) {
            // For interrupt responses (architect), replace the message
            if (data.is_interrupt) {
              currentAgentMessage = data.token

              // Update node if provided
              if (data.agent_node) {
                currentNode = data.agent_node
                setActiveNode(data.agent_node)
              }

              // Update instruction if provided
              if (data.instruction) {
                setInstruction(data.instruction)
              }

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
              currentAgentMessage += data.token
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
      const lastMsgIdx = newMessages.length - 1
      if (lastMsgIdx >= 0) {
        if (isPlannerStreaming) {
          // For planner: store the actual plan content in planContent field
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            content: 'Plan generated', // Display text (not shown in UI since we use compact card)
            planContent: currentAgentMessage, // Store actual plan content here
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
      <div className="flex-1 overflow-y-auto px-6 py-6 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="text-5xl mb-4 opacity-20">⚡</div>
              <p className="text-lg text-warm-beige/70 mb-2 font-light">
                Start a new workflow
              </p>
              <p className="text-sm text-warm-beige/50 font-light">
                Describe what you want to accomplish
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
                {/* Planner message - Compact card view */}
                {message.node?.includes('planner') && message.role === 'agent' ? (
                  <div className="rounded-lg bg-warm-gray/30 border border-warm-teal/30 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-warm-teal/20 flex items-center justify-center">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-warm-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                          </svg>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-warm-beige">Project Plan</span>
                            {message.isLoading || (isPlannerStreaming && idx === messages.length - 1) ? (
                              <div className="flex items-center gap-1">
                                <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                              </div>
                            ) : (
                              <div className="w-2 h-2 rounded-full bg-warm-teal" />
                            )}
                          </div>
                          <p className="text-xs text-warm-beige/50">
                            {message.isLoading || (isPlannerStreaming && idx === messages.length - 1)
                              ? 'Generating plan...'
                              : 'Plan generated successfully'}
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
                        disabled={!message.planContent && !isPlannerStreaming}
                        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${!message.planContent && !isPlannerStreaming
                          ? 'bg-warm-gray/40 text-warm-beige/40 cursor-not-allowed'
                          : isPlanViewerOpen && currentViewingPlanContent === message.planContent
                            ? 'bg-warm-teal/20 text-warm-teal border border-warm-teal/40 hover:bg-warm-teal/30'
                            : 'bg-warm-teal text-warm-dark hover:bg-warm-teal/90'
                          }`}
                      >
                        {isPlanViewerOpen && currentViewingPlanContent === message.planContent ? (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                            </svg>
                            Hide Plan
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            View Plan
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Regular message display for user and architect */
                  <div
                    className={`max-w-[85%] rounded-lg ${message.role === 'user'
                      ? 'bg-warm-amber/15 text-warm-beige border border-warm-amber/20'
                      : 'bg-warm-gray/30 text-warm-beige border border-warm-gray/40'
                      }`}
                  >
                    {/* Architect badge */}
                    {message.node?.includes('architect') && message.role === 'agent' && !message.isLoading && message.content && (
                      <div className="flex items-center gap-2 px-4 pt-3 pb-0">
                        <div className="w-2 h-2 rounded-full bg-warm-amber" />
                        <span className="text-xs font-medium text-warm-amber uppercase tracking-wider">Architect</span>
                      </div>
                    )}
                    <div className={`px-4 py-4`}>
                      {message.isLoading ? (
                        <div className="flex items-center gap-1.5 py-1">
                          <div className="w-2 h-2 bg-warm-amber rounded-full animate-pulse"></div>
                          <div className="w-2 h-2 bg-warm-amber rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                          <div className="w-2 h-2 bg-warm-amber rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                        </div>
                      ) : message.role === 'agent' ? (
                        <div className="prose prose-sm prose-invert max-w-none prose-headings:text-warm-amber prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2 prose-p:text-warm-beige prose-p:my-2 prose-li:text-warm-beige prose-li:my-0.5 prose-strong:text-warm-amber prose-code:text-warm-amber prose-code:bg-warm-gray/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-warm-gray/50 prose-pre:border prose-pre:border-warm-gray/40 prose-ul:my-2 prose-ol:my-2">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="text-sm leading-relaxed">
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
        <div className="px-6 py-3 border-t border-warm-gray/30 bg-warm-amber/5">
          <p className="text-xs text-warm-amber/80 font-medium max-w-4xl mx-auto">
            {instruction}
          </p>
        </div>
      )}

      {/* Input Area */}
      <div className="px-6 py-5 border-t border-warm-gray/30 bg-warm-gray/10">
        <form onSubmit={!threadId ? (e) => handleStartWorkflow(e, null) : handleSubmit}>
          <div className="flex gap-3 max-w-4xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                threadId
                  ? 'Type your response...'
                  : 'Describe your task to start the workflow...'
              }
              className="flex-1 bg-warm-gray/20 border border-warm-gray/40 rounded-lg px-4 py-3 text-sm text-warm-beige placeholder-warm-beige/40 focus:outline-none focus:border-warm-amber/40 focus:bg-warm-gray/30 transition-all"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="px-6 py-3 bg-warm-amber text-warm-dark text-sm font-medium rounded-lg hover:bg-warm-amber/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all disabled:hover:bg-warm-amber"
            >
              {!threadId ? 'Start' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
