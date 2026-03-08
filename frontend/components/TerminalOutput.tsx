'use client'

import { useEffect, useRef } from 'react'

interface TerminalOutputProps {
    logs: string[]
    onClose: () => void
}

export default function TerminalOutput({ logs, onClose }: TerminalOutputProps) {
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [logs])

    return (
        <div className="flex flex-col h-full bg-[#000000] border-l border-white/5 rounded-none overflow-hidden pb-4">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-white/[0.02] flex-shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                    <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                    <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                    <span className="ml-3 text-[10px] font-mono uppercase tracking-[0.2em] text-white/50 font-medium">
                        Terminal
                    </span>
                </div>
                <button
                    onClick={onClose}
                    className="text-white/30 hover:text-white transition-colors"
                    title="Close terminal"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {/* Logs */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-5 font-mono text-[10px] leading-relaxed custom-scrollbar"
            >
                {logs.length === 0 ? (
                    <div className="text-white/20 italic tracking-wide">Awaiting command output...</div>
                ) : (
                    logs.map((log, idx) => (
                        <div key={idx} className="mb-1.5 whitespace-pre-wrap">
                            {log.startsWith('🔧') ? (
                                <span className="text-platinum-muted opacity-80">{log}</span>
                            ) : log.includes('Exit Code: 0') ? (
                                <span className="text-emerald-400/90">{log}</span>
                            ) : log.includes('Exit Code:') ? (
                                <span className="text-red-400/90">{log}</span>
                            ) : (
                                <span className="text-white/70">{log}</span>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}
