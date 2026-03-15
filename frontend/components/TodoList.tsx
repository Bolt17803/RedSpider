import { useState, useEffect } from 'react'

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
    textClass: 'text-white/40',
    bgClass: 'bg-white/[0.01] border-white/[0.04]',
    iconClass: 'text-white/20',
  },
  in_progress: {
    icon: '◉',
    textClass: 'text-gold-light',
    bgClass: 'bg-gold-accent/[0.05] border-gold-accent/20',
    iconClass: 'text-gold-accent animate-pulse-soft text-glow-accent',
  },
  completed: {
    icon: '✓',
    textClass: 'text-cyan-300/70 line-through',
    bgClass: 'bg-electric-cyan/[0.04] border-electric-cyan/20',
    iconClass: 'text-electric-cyan text-glow',
  },
}

export default function TodoList({ todos }: { todos: TodoItem[] }) {
  const [maxCount, setMaxCount] = useState(0)

  useEffect(() => {
    if (todos && todos.length > maxCount) {
      setMaxCount(todos.length)
    }
  }, [todos, maxCount])

  if (!todos || todos.length === 0) return null

  const currentCompleted = todos.filter((t) => t.status === 'completed').length
  const inferredCompleted = Math.max(0, maxCount - todos.length)
  const totalCompleted = currentCompleted + inferredCompleted
  const totalDisplayCount = Math.max(todos.length, maxCount)
  const pct = totalDisplayCount ? Math.round((totalCompleted / totalDisplayCount) * 100) : 0

  return (
    <div className="rounded-xl glass-premium p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-platinum/80 uppercase tracking-[0.2em]">
          TODO Tasks
        </span>
        <span className="text-[11px] text-white/40 font-mono tracking-widest">
          {totalCompleted}/{totalDisplayCount}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-white/30 font-mono tracking-wider">
          <span>PROGRESS</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden shadow-inner flex">
          <div
            className="h-full rounded-full bg-gradient-to-r from-electric-blue via-electric-cyan to-electric-cyan transition-all duration-700 ease-out shadow-[0_0_10px_rgba(6,182,212,0.5)]"
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
