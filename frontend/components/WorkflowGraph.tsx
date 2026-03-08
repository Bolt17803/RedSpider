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
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
  {
    id: 'planner_agent',
    label: 'Planner',
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
  {
    id: 'coder_agent',
    label: 'Coder',
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
  {
    id: 'validation_agent',
    label: 'Validator',
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
  {
    id: 'summarizer_agent',
    label: 'Summarizer',
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
  {
    id: 'human_response',
    label: 'Review',
    color: '#ffffff',
    glowColor: 'rgba(255, 255, 255, 0.6)',
  },
]

const connections = [
  { from: 0, to: 1 },
  { from: 1, to: 2 },
  { from: 2, to: 3 },
  { from: 3, to: 4 },
  { from: 4, to: 5 },
]

export default function WorkflowGraph({ activeNode }: WorkflowGraphProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-white/30 text-xs tracking-widest uppercase">Loading...</div>
      </div>
    )
  }

  const getNodeStatus = (nodeId: string) => {
    if (!activeNode) return 'inactive'

    // Direct match
    if (activeNode === nodeId) return 'active'

    // Map ALL backend node names → graph node IDs
    const nodeMap: Record<string, string> = {
      // Architect variants
      'architect': 'architect_agent',
      'architect_review': 'architect_agent',
      'architect_review_node': 'architect_agent',
      'architect_response_review_node': 'architect_agent',
      // Planner variants
      'planner': 'planner_agent',
      'planner_review': 'planner_agent',
      'planner_review_node': 'planner_agent',
      'planner_response_review_node': 'planner_agent',
      // Coder
      'coder': 'coder_agent',
      // Validation
      'validation': 'validation_agent',
      'validator': 'validation_agent',
      // Summarizer
      'summarizer': 'summarizer_agent',
      // Init maps to architect (first step)
      'init_deepagents': 'architect_agent',
    }

    const mappedId = nodeMap[activeNode]
    if (mappedId === nodeId) return 'active'

    return 'inactive'
  }

  return (
    <div className="relative h-full flex items-center justify-center">
      <svg
        className="w-full h-full max-h-[500px]"
        viewBox="0 0 60 450"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Glow filter definition */}
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connections */}
        <g strokeWidth="1" fill="none">
          {connections.map((conn, idx) => {
            const fromY = 30 + conn.from * 55
            const toY = 30 + conn.to * 55
            const fromNode = nodes[conn.from]
            const toNode = nodes[conn.to]
            const isFromActive = getNodeStatus(fromNode.id) === 'active'
            const isToActive = getNodeStatus(toNode.id) === 'active'

            return (
              <line
                key={idx}
                x1="30"
                y1={fromY}
                x2="30"
                y2={toY}
                stroke={isFromActive || isToActive ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}
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

              {/* Node circle - always visible */}
              <circle
                cx="30"
                cy={y}
                r="7"
                fill={isActive ? node.color : 'transparent'}
                stroke={isActive ? node.color : 'rgba(255, 255, 255, 0.2)'}
                strokeWidth={isActive ? '2' : '1.5'}
                filter={isActive ? 'url(#glow)' : 'none'}
              />

              {/* Node label */}
              <text
                x="30"
                y={y + 22}
                textAnchor="middle"
                fill={isActive ? node.color : 'rgba(255, 255, 255, 0.35)'}
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
