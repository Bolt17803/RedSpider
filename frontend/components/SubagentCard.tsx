'use client'

import { useState, useEffect } from 'react'

export interface SubagentInfo {
  id: string              // node name e.g. "coder_agent"
  label: string           // human label e.g. "Coder"
  status: 'pending' | 'running' | 'complete' | 'error'
  startedAt?: number      // epoch ms
  completedAt?: number    // epoch ms
  lastContent: string     // latest streamed text
}

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  running: '◉',
  complete: '✓',
  error: '✗',
}

const STATUS_COLORS: Record<string, {
  icon: string
  badge: string
  badgeText: string
  border: string
}> = {
  pending: {
    icon: 'text-text-tertiary',
    badge: 'bg-white/5 border-border-subtle',
    badgeText: 'text-text-tertiary',
    border: 'border-border-subtle',
  },
  running: {
    icon: 'text-accent-indigo animate-pulse-subtle',
    badge: 'bg-accent-indigo/10 border-accent-indigo/30',
    badgeText: 'text-accent-indigo',
    border: 'border-accent-indigo/20 shadow-[0_0_15px_rgba(99,102,241,0.05)]',
  },
  complete: {
    icon: 'text-text-secondary',
    badge: 'bg-white/10 border-border-focus',
    badgeText: 'text-text-primary',
    border: 'border-border-subtle hover:border-border-focus',
  },
  error: {
    icon: 'text-red-500',
    badge: 'bg-red-500/10 border-red-500/30',
    badgeText: 'text-red-400',
    border: 'border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.05)]',
  },
}

function getElapsedTime(startedAt?: number, completedAt?: number): string | null {
  if (!startedAt) return null
  const end = completedAt ?? Date.now()
  const seconds = Math.round((end - startedAt) / 1000)
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

export default function SubagentCard({ subagent }: { subagent: SubagentInfo }) {
  const [expanded, setExpanded] = useState(true)
  const [elapsed, setElapsed] = useState<string | null>(null)

  const colors = STATUS_COLORS[subagent.status] ?? STATUS_COLORS.pending

  // Live elapsed time counter
  useEffect(() => {
    setElapsed(getElapsedTime(subagent.startedAt, subagent.completedAt))

    if (subagent.status === 'running' && subagent.startedAt) {
      const interval = setInterval(() => {
        setElapsed(getElapsedTime(subagent.startedAt, undefined))
      }, 1000)
      return () => clearInterval(interval)
    }
  }, [subagent.status, subagent.startedAt, subagent.completedAt])

  return (
    <div className={`rounded-xl surface-panel shadow-lg transition-all duration-300 ${colors.border}`}>
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-5 py-3.5"
      >
        <div className="flex items-center gap-4">
          {/* Status icon */}
          <span className={`text-xl leading-none ${colors.icon}`}>
            {STATUS_ICON[subagent.status] ?? '○'}
          </span>
          <div className="text-left">
            <h4 className="text-[11px] font-heading font-semibold uppercase tracking-widest text-text-primary">
              {subagent.label}
            </h4>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {elapsed && (
            <span className="text-[11px] text-text-tertiary font-mono tracking-widest">{elapsed}</span>
          )}
          {/* Status badge */}
          <span className={`text-[9px] uppercase tracking-[0.2em] font-medium px-3 py-1.5 rounded-full border ${colors.badge} ${colors.badgeText} transition-colors duration-300`}>
            {subagent.status}
          </span>
          {/* Expand/collapse chevron */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`h-4 w-4 text-text-tertiary transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Body — collapsible */}
      {expanded && subagent.lastContent && (
        <div className="border-t border-border-subtle px-5 py-4 bg-pure-black/40">
          <div className="text-[12px] text-text-secondary font-mono leading-relaxed max-h-96 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
            {subagent.lastContent}
            {subagent.status === 'running' && (
              <span className="inline-block h-3 w-1.5 ml-1 animate-pulse bg-accent-indigo align-bottom" />
            )}
          </div>
          {/* Show "thinking..." label while running to signal this is live reasoning */}
          {subagent.status === 'running' && (
            <div className="mt-2 flex items-center gap-1.5">
              <span className="text-[9px] uppercase tracking-[0.2em] text-text-tertiary font-medium">
                Thinking...
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
