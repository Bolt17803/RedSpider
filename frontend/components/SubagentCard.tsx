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
    icon: 'text-white/30',
    badge: 'bg-white/5 border-white/10',
    badgeText: 'text-white/40',
    border: 'border-white/[0.04]',
  },
  running: {
    icon: 'text-gold-accent animate-pulse-soft text-glow-accent',
    badge: 'bg-gold-accent/10 border-gold-accent/30',
    badgeText: 'text-gold-light',
    border: 'border-gold-accent/20 shadow-[0_0_15px_rgba(212,175,55,0.05)]',
  },
  complete: {
    icon: 'text-electric-cyan text-glow',
    badge: 'bg-electric-cyan/10 border-electric-cyan/30',
    badgeText: 'text-cyan-300',
    border: 'border-electric-cyan/20 shadow-[0_0_15px_rgba(6,182,212,0.05)]',
  },
  error: {
    icon: 'text-red-500 text-glow',
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
    <div className={`rounded-xl glass-premium shadow-lg transition-all duration-500 ${colors.border}`}>
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
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-platinum/90">
              {subagent.label}
            </h4>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {elapsed && (
            <span className="text-[11px] text-white/40 font-mono tracking-widest">{elapsed}</span>
          )}
          {/* Status badge */}
          <span className={`text-[9px] uppercase tracking-[0.2em] font-medium px-3 py-1.5 rounded-full border ${colors.badge} ${colors.badgeText} transition-colors duration-500`}>
            {subagent.status}
          </span>
          {/* Expand/collapse chevron */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`h-4 w-4 text-white/30 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}
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
        <div className="border-t border-white/[0.04] px-5 py-4 bg-black/10">
          <div className="text-[11px] text-platinum-muted font-mono leading-relaxed max-h-40 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
            {subagent.lastContent}
            {subagent.status === 'running' && (
              <span className="inline-block h-3 w-1 ml-1 animate-pulse bg-gold-accent align-bottom shadow-[0_0_8px_rgba(212,175,55,0.6)]" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
