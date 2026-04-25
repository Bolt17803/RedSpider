'use client'

import { useEffect, useState } from 'react'

interface WorkflowGraphProps {
  activeNode: string | null
}

interface NodeData {
  id: string
  label: string
}

const nodes: NodeData[] = [
  { id: 'architect_agent', label: 'Architect' },
  { id: 'planner_agent',   label: 'Planner'   },
  { id: 'coder_agent',     label: 'Coder'     },
  { id: 'validation_agent',label: 'Validator' },
  { id: 'summarizer_agent',label: 'Summarizer'},
  { id: 'human_response',  label: 'Review'    },
]

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
        <div className="text-text-tertiary text-xs tracking-widest uppercase animate-pulse">Loading Pipeline...</div>
      </div>
    )
  }

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
    <div className="relative h-full flex flex-col py-6 px-4 custom-scrollbar overflow-y-auto w-full">
       {nodes.map((node, idx) => {
         const status = getStatus(idx)
         const isActive = status === 'active'
         const isCompleted = status === 'completed'
         
         return (
           <div key={node.id} className="relative flex items-start group">
              {/* Connector Line */}
              {idx !== nodes.length - 1 && (
                 <div className="absolute left-[11px] top-6 bottom-[-8px] w-0.5">
                    <div className={`w-full h-full transition-all duration-700 ${isCompleted ? 'bg-accent-indigo/60' : 'bg-white/5'}`}></div>
                 </div>
              )}
              
              {/* Node Indicator */}
              <div className="relative z-10 flex-shrink-0 mt-0.5 mr-4">
                 <div className={`w-6 h-6 rounded-full flex items-center justify-center border transition-all duration-500
                    ${isActive ? 'border-accent-indigo bg-accent-indigo/10 shadow-[0_0_15px_rgba(99,102,241,0.25)]' : 
                      isCompleted ? 'border-accent-indigo bg-accent-indigo' : 'border-border-subtle bg-charcoal-base'}`}
                 >
                    {isActive && (
                       <span className="w-2.5 h-2.5 rounded-full bg-accent-indigo animate-pulse"></span>
                    )}
                    {isCompleted && (
                       <svg className="w-3.5 h-3.5 text-pure-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                       </svg>
                    )}
                    {!isActive && !isCompleted && (
                       <span className="w-1.5 h-1.5 rounded-full bg-text-tertiary/50"></span>
                    )}
                 </div>
              </div>
              
              {/* Node Label */}
              <div className={`pb-10 -mt-0.5 transition-colors duration-300
                 ${isActive ? 'text-text-primary' : isCompleted ? 'text-text-secondary' : 'text-text-tertiary'}`}
              >
                 <span className="text-xs font-heading font-semibold tracking-wide block">{node.label}</span>
                 {isActive && (
                   <div className="text-[10px] uppercase tracking-widest text-accent-indigo font-medium mt-1.5 flex items-center gap-1 opacity-80">
                     <span>Processing</span>
                     <span className="flex gap-0.5 ml-1">
                        <span className="w-1 h-1 rounded-full bg-current animate-bounce" style={{ animationDelay: '0ms' }}></span>
                        <span className="w-1 h-1 rounded-full bg-current animate-bounce" style={{ animationDelay: '150ms' }}></span>
                        <span className="w-1 h-1 rounded-full bg-current animate-bounce" style={{ animationDelay: '300ms' }}></span>
                     </span>
                   </div>
                 )}
                 {isCompleted && (
                     <span className="text-[9px] uppercase tracking-[0.2em] text-text-tertiary mt-1 block">Verified</span>
                 )}
              </div>
           </div>
         )
       })}
    </div>
  )
}
