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
    <div className="h-full flex flex-col bg-warm-darker/80 backdrop-blur-sm rounded-xl border border-warm-gray/40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-warm-gray/30 bg-warm-gray/20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-warm-teal animate-pulse' : 'bg-warm-amber'}`} />
            <h3 className="text-sm font-medium text-warm-beige">
              {isStreaming ? 'Generating Plan...' : 'Project Plan'}
            </h3>
          </div>
          {isStreaming && (
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1.5 h-1.5 bg-warm-teal rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-warm-beige/60 hover:text-warm-beige hover:bg-warm-gray/40 rounded-lg transition-all"
          title="Close plan viewer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div 
        ref={contentRef}
        className="flex-1 overflow-y-auto p-4"
      >
        {content ? (
          <div className="prose prose-sm prose-invert max-w-none prose-headings:text-warm-teal prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2 prose-p:text-warm-beige/90 prose-p:my-2 prose-li:text-warm-beige/90 prose-li:my-0.5 prose-strong:text-warm-amber prose-code:text-warm-amber prose-code:bg-warm-gray/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-warm-gray/50 prose-pre:border prose-pre:border-warm-gray/40 prose-ul:my-2 prose-ol:my-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-warm-teal/80 animate-pulse ml-1" />
            )}
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-warm-beige/40">
              <div className="text-3xl mb-2">📋</div>
              <p className="text-sm">Waiting for plan...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

