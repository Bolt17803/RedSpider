'use client'

import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface PlanViewerProps {
  content: string
  isStreaming: boolean
  onClose: () => void
}

export default function PlanViewer({ content, isStreaming, onClose }: PlanViewerProps) {
  const contentRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom while streaming
  useEffect(() => {
    if (isStreaming && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [content, isStreaming])

  return (
    <div className="h-full flex flex-col bg-charcoal-base border border-border-subtle rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="h-10 flex items-center justify-between border-b border-border-subtle bg-charcoal-surface px-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-accent-indigo animate-pulse' : 'bg-emerald-500'}`} />
            <h3 className="text-xs font-heading font-medium tracking-wide text-text-primary uppercase">
              {isStreaming ? 'Synthesizing Plan...' : 'Project Blueprint'}
            </h3>
          </div>
          {isStreaming && (
            <div className="flex items-center gap-1 opacity-80">
              <div className="w-1 h-1 bg-accent-indigo rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1 h-1 bg-accent-indigo rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1 h-1 bg-accent-indigo rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-text-tertiary hover:text-text-primary hover:bg-white/10 transition-colors"
          title="Close plan viewer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div 
        ref={contentRef}
        className="flex-1 overflow-y-auto overflow-x-hidden p-5 bg-[#0d0d0d] custom-scrollbar break-words"
      >
        {content ? (
          <div className="prose prose-sm prose-invert max-w-none 
            prose-headings:text-text-primary prose-headings:font-heading prose-headings:font-medium prose-headings:tracking-wide prose-headings:mt-6 prose-headings:mb-3 
            prose-p:text-text-secondary prose-p:leading-relaxed prose-p:my-2 
            prose-li:text-text-secondary prose-li:my-0.5 
            prose-strong:text-text-primary prose-strong:font-semibold
            prose-code:text-accent-indigo prose-code:bg-white/5 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:text-[13px]
            prose-pre:bg-pure-black/60 prose-pre:border prose-pre:border-border-subtle prose-pre:rounded-lg prose-pre:overflow-x-auto
            prose-ul:my-2 prose-ol:my-2 text-[14px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-accent-indigo/80 animate-pulse ml-1 align-middle" />
            )}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-text-tertiary">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 mb-3 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
            <p className="text-xs tracking-wider uppercase">Awaiting Architectural Plan...</p>
          </div>
        )}
      </div>
    </div>
  )
}

