import { useState } from 'react'

interface TodoItem {
  status: 'pending' | 'in_progress' | 'completed'
  content: string
  title?: string
}

const STATUS_CONFIG: Record<string, {
  icon: string
  textClass: string
  bgClass: string
  iconClass: string
}> = {
  pending: {
    icon: '○',
    textClass: 'text-text-tertiary',
    bgClass: 'bg-white/5 border-border-subtle',
    iconClass: 'text-text-tertiary',
  },
  in_progress: {
    icon: '◉',
    textClass: 'text-accent-indigo',
    bgClass: 'bg-accent-indigo/10 border-accent-indigo/20',
    iconClass: 'text-accent-indigo animate-pulse-subtle',
  },
  completed: {
    icon: '✓',
    textClass: 'text-text-secondary line-through',
    bgClass: 'bg-white/10 border-border-focus',
    iconClass: 'text-text-primary',
  },
}

export default function TodoList({ todos }: { todos: TodoItem[] }) {
  if (!todos || todos.length === 0) return null

  // FIX: use actual status counts — no more inferring from list length changes.
  // The agent now reliably calls write_todos() after each task with real statuses.
  const completed = todos.filter(t => t.status === 'completed').length
  const total = todos.length
  const pct = total ? Math.round((completed / total) * 100) : 0

  return (
    <div className="rounded-xl surface-panel p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-heading font-medium text-text-primary uppercase tracking-widest">
          TODO Tasks
        </span>
        <span className="text-[11px] text-text-tertiary font-mono tracking-widest">
          {completed}/{total}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-text-tertiary font-mono tracking-wider">
          <span>PROGRESS</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-pure-black border border-border-subtle overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent-indigo to-accent-indigo transition-all duration-700 ease-out shadow-sm"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Todo items */}
      <ul className="space-y-2">
        {todos.map((todo, i) => {
          const style = STATUS_CONFIG[todo.status] ?? STATUS_CONFIG.pending
          return (
            <li
              key={i}
              className={`flex items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-300 ${style.bgClass}`}
            >
              <span className={`mt-0.5 text-sm leading-none flex-shrink-0 ${style.iconClass}`}>
                {style.icon}
              </span>
              <span className={`text-[11px] leading-relaxed ${style.textClass}`}>
                {todo.title || todo.content}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
