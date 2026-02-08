'use client'

import { useEffect, useState } from 'react'

interface WorkflowGraphProps {
  activeNode: string | null
}

interface NodeData {
  id: string
  label: string
  color: string
  glowColor: string
}

const nodes: NodeData[] = [
  {
    id: 'architect_agent',
    label: 'Architect',
    color: '#f59e0b',
    glowColor: 'rgba(245, 158, 11, 0.6)',
  },
  {
    id: 'planner_agent',
    label: 'Planner',
    color: '#f59e0b',
    glowColor: 'rgba(245, 158, 11, 0.6)',
  },
  {
    id: 'coder',
    label: 'Coder',
    color: '#f59e0b',
    glowColor: 'rgba(245, 158, 11, 0.6)',
  },
]

const connections = [
  { from: 0, to: 1 },
  { from: 1, to: 2 },
]

export default function WorkflowGraph({ activeNode }: WorkflowGraphProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-warm-beige/30 text-xs">Loading...</div>
      </div>
    )
  }

  const getNodeStatus = (nodeId: string) => {
    if (!activeNode) return 'inactive'
    
    // Direct matches
    if (activeNode === nodeId) {
      return 'active'
    }
    
    // Map backend node names to graph IDs
    if (activeNode === 'architect' && nodeId === 'architect_agent') return 'active'
    // Map architect_review to architect_agent (keep architect active during review)
    if (activeNode === 'architect_review_node' && nodeId === 'architect_agent') return 'active'
    if (activeNode === 'architect_review' && nodeId === 'architect_agent') return 'active'
    
    if (activeNode === 'planner' && nodeId === 'planner_agent') return 'active'
    // Map planner_review to planner_agent (keep planner active during review)
    if (activeNode === 'planner_review_node' && nodeId === 'planner_agent') return 'active'
    if (activeNode === 'planner_review' && nodeId === 'planner_agent') return 'active'
    
    if (activeNode === 'coder' && nodeId === 'coder') return 'active'
    
    return 'inactive'
  }

  return (
    <div className="relative h-full flex items-center justify-center">
      <svg
        className="w-full h-full max-h-[350px]"
        viewBox="0 0 60 300"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Glow filter definition */}
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Connections */}
        <g stroke="rgba(245, 158, 11, 0.1)" strokeWidth="1" fill="none">
          {connections.map((conn, idx) => {
            const fromY = 30 + conn.from * 55
            const toY = 30 + conn.to * 55

            return (
              <line
                key={idx}
                x1="30"
                y1={fromY}
                x2="30"
                y2={toY}
                strokeDasharray="2,2"
              />
            )
          })}
        </g>

        {/* Nodes */}
        {nodes.map((node, idx) => {
          const y = 30 + idx * 55
          const isActive = getNodeStatus(node.id) === 'active'

          return (
            <g key={node.id}>
              {/* Outer glow for active node */}
              {isActive && (
                <>
                  <circle
                    cx="30"
                    cy={y}
                    r="14"
                    fill={node.color}
                    opacity="0.3"
                  >
                    <animate
                      attributeName="opacity"
                      values="0.3;0.6;0.3"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                  </circle>
                  <circle
                    cx="30"
                    cy={y}
                    r="10"
                    fill={node.color}
                    opacity="0.5"
                  >
                    <animate
                      attributeName="opacity"
                      values="0.5;0.8;0.5"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                  </circle>
                </>
              )}

              {/* Node circle - transparent when inactive, bright when active */}
              <circle
                cx="30"
                cy={y}
                r="7"
                fill={isActive ? node.color : 'transparent'}
                opacity={isActive ? '1' : '0'}
                stroke={isActive ? node.color : 'rgba(245, 158, 11, 0.15)'}
                strokeWidth={isActive ? '2' : '1'}
                filter={isActive ? 'url(#glow)' : 'none'}
              />

              {/* Node label */}
              <text
                x="30"
                y={y + 22}
                textAnchor="middle"
                fill={isActive ? 'rgba(245, 158, 11, 1)' : 'rgba(245, 235, 224, 0.25)'}
                fontSize="8"
                fontWeight={isActive ? '700' : '400'}
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
