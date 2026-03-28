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
