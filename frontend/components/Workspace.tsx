'use client'

import { useState } from 'react'
import WorkflowGraph from '@/components/WorkflowGraph'
import ChatInterface from '@/components/ChatInterface'
import PlanViewer from '@/components/PlanViewer'
import TerminalOutput from '@/components/TerminalOutput'
import CodeViewer from '@/components/CodeViewer'

interface WorkspaceProps {
    onHome: () => void
    projectTitle?: string
    initialThreadId?: string | null
    shouldLoadHistory?: boolean
}

export default function Workspace({ onHome, projectTitle, initialThreadId, shouldLoadHistory }: WorkspaceProps) {
    const [activeNode, setActiveNode] = useState<string | null>(null)
    const [threadId, setThreadId] = useState<string | null>(initialThreadId || null)
    const [showPlanViewer, setShowPlanViewer] = useState(false)
    const [planContent, setPlanContent] = useState('')
    const [isPlanStreaming, setIsPlanStreaming] = useState(false)
    const [terminalLogs, setTerminalLogs] = useState<string[]>([])
    const [showTerminal, setShowTerminal] = useState(false)
    const [showCodeViewer, setShowCodeViewer] = useState(false)
    const [isCodeViewerFullscreen, setIsCodeViewerFullscreen] = useState(false)

    // Handle plan updates from ChatInterface (during streaming)
    const handlePlanUpdate = (content: string, isStreaming: boolean) => {
        setPlanContent(content)
        setIsPlanStreaming(isStreaming)
        // Auto-open plan viewer when planner starts streaming
        if (isStreaming && !showPlanViewer) {
            setShowPlanViewer(true)
        }
    }

    // Handle viewing a specific plan (from clicking View Plan button)
    const handleViewPlan = (content: string) => {
        setPlanContent(content)
        setIsPlanStreaming(false)
        setShowPlanViewer(true)
    }

    // Handle closing the plan viewer
    const handleClosePlanViewer = () => {
        setShowPlanViewer(false)
    }

    const handleTerminalLog = (log: string) => {
        setTerminalLogs(prev => [...prev, log])
        // Auto-open terminal when first command output arrives
        if (!showTerminal) {
            setShowTerminal(true)
        }
    }

    const handleWorkflowComplete = (finalTodos: any[]) => {
        setActiveNode(null)
    }

    return (
        <div className="flex h-screen bg-pure-black text-text-primary font-sans overflow-hidden">
            <div className="flex-1 flex flex-col min-w-0">
                {/* Application Header - Minimalist */}
                <header className="h-14 border-b border-border-subtle flex items-center justify-between px-6 bg-charcoal-base z-10 flex-shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-6 h-6 rounded bg-accent-indigo text-pure-black font-heading font-bold text-xs">
                            Tr
                        </div>
                        <h1 className="text-xs font-heading font-medium tracking-wide text-text-secondary">Tarantula</h1>
                        {projectTitle && (
                            <>
                                <span className="text-border-subtle">/</span>
                                <span className="text-xs font-medium text-text-primary">{projectTitle}</span>
                            </>
                        )}
                        {threadId && (
                            <span className="text-[10px] font-mono text-text-tertiary ml-2 px-1.5 py-0.5 rounded border border-border-subtle">
                                {threadId.substring(0, 8)}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setShowTerminal(!showTerminal)}
                            className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-md transition-all border ${showTerminal
                                ? 'bg-white/10 border-white/20 text-text-primary shadow-[0_0_12px_rgba(255,255,255,0.05)]'
                                : 'bg-transparent border-transparent hover:bg-white/5 hover:border-border-subtle text-text-secondary'
                                }`}
                            title="Toggle Terminal"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <span className="font-medium">Terminal</span>
                            {terminalLogs.length > 0 && !showTerminal && (
                                <span className="ml-1 px-1 min-w-[16px] h-4 rounded-full bg-accent-indigo text-[9px] font-bold text-pure-black flex items-center justify-center">
                                    {terminalLogs.length > 9 ? '9+' : terminalLogs.length}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => setShowCodeViewer(!showCodeViewer)}
                            className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-md transition-all border ${showCodeViewer
                                ? 'bg-white/10 border-white/20 text-text-primary shadow-[0_0_12px_rgba(255,255,255,0.05)]'
                                : 'bg-transparent border-transparent hover:bg-white/5 hover:border-border-subtle text-text-secondary'
                                }`}
                            title="Toggle Code Explorer"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                            </svg>
                            <span className="font-medium">Code</span>
                        </button>
                        <div className="w-px h-4 bg-border-subtle mx-1"></div>
                        <button
                            onClick={onHome}
                            className="text-xs font-medium px-3 py-1.5 bg-transparent rounded-md transition-all text-text-tertiary hover:text-text-primary hover:bg-white/5"
                        >
                            Exit
                        </button>
                    </div>
                </header>

                {/* Subdued Status Banner */}
                {activeNode && !['architect_agent', 'architect_review'].includes(activeNode) && (
                    <div className="h-8 border-b border-border-subtle flex items-center px-6 bg-charcoal-surface">
                        <div className="flex items-center gap-3 text-xs">
                            <div className="relative flex h-1.5 w-1.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-indigo opacity-70"></span>
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent-indigo"></span>
                            </div>
                            <span className="font-mono text-text-tertiary uppercase tracking-wider text-[10px]">[{activeNode.split('_')[0]}]</span>
                            <span className="font-medium text-text-secondary">
                                {activeNode.includes('init') ? 'Initializing system...' :
                                    activeNode.includes('planner') ? 'Architecting blueprint...' :
                                        activeNode.includes('coder') ? 'Synthesizing implementation...' :
                                            activeNode.includes('validation') ? 'Verifying codebase integrity...' :
                                                activeNode.includes('tester') ? 'Executing test suite...' :
                                                    activeNode.includes('human') ? 'Awaiting human authorization...' :
                                                        'Processing state transition...'}
                            </span>
                        </div>
                    </div>
                )}

                {/* Main Content Panels */}
                <div className="flex-1 flex gap-4 p-4 min-h-0 bg-charcoal-base">
                    
                    {/* Graph Topology Panel */}
                    <div className="w-56 flex-shrink-0 flex flex-col pt-1 surface-panel rounded-lg p-3 overflow-hidden">
                        <div className="flex items-center gap-2 mb-4 px-1">
                            <svg className="w-4 h-4 text-text-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                            </svg>
                            <h2 className="text-xs font-heading font-medium text-text-secondary tracking-wide uppercase">
                                Execution Pipeline
                            </h2>
                        </div>
                        <div className="flex-1 min-h-0 overflow-hidden px-1">
                            <WorkflowGraph activeNode={activeNode} />
                        </div>
                    </div>

                    {/* Dynamic Panels Container */}
                    <div className="flex-1 min-h-0 min-w-0 flex gap-4">
                        
                        {/* Plan Viewer Panel */}
                        {showPlanViewer && (
                            <div className="w-1/3 min-w-0 flex flex-col surface-panel rounded-lg overflow-hidden animate-fade-in-up transition-all">
                                <PlanViewer
                                    content={planContent}
                                    isStreaming={isPlanStreaming}
                                    onClose={handleClosePlanViewer}
                                />
                            </div>
                        )}

                        {/* Code Explorer Panel */}
                        {showCodeViewer && projectTitle && (
                            <div className={`${isCodeViewerFullscreen ? 'absolute inset-4 z-50' : 'w-[45%] min-w-[500px]'} flex flex-col surface-panel rounded-lg overflow-hidden animate-fade-in-up transition-all shadow-2xl`}>
                                <CodeViewer
                                    projectId={projectTitle}
                                    onClose={() => {
                                        setShowCodeViewer(false)
                                        setIsCodeViewerFullscreen(false)
                                    }}
                                    isExpanded={isCodeViewerFullscreen}
                                    onToggleExpand={() => setIsCodeViewerFullscreen(!isCodeViewerFullscreen)}
                                />
                            </div>
                        )}

                        {/* Terminal Panel */}
                        {showTerminal && (
                            <div className="w-1/3 min-w-0 flex flex-col surface-panel rounded-lg overflow-hidden animate-fade-in-up transition-all">
                                <TerminalOutput
                                    logs={terminalLogs}
                                    onClose={() => setShowTerminal(false)}
                                />
                            </div>
                        )}

                        {/* Essential Chat Interface Panel */}
                        <div className="flex-1 min-w-0 flex flex-col surface-panel rounded-lg overflow-hidden relative">
                            {/* Subtle embedded header gradient for depth */}
                            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-white/[0.03] to-transparent pointer-events-none z-0"></div>
                            
                            <div className="relative z-10 flex-1 min-h-0 flex flex-col">
                                <ChatInterface
                                    activeNode={activeNode}
                                    setActiveNode={setActiveNode}
                                    threadId={threadId}
                                    setThreadId={setThreadId}
                                    shouldLoadHistory={shouldLoadHistory}
                                    onPlanUpdate={handlePlanUpdate}
                                    onViewPlan={handleViewPlan}
                                    onClosePlanViewer={handleClosePlanViewer}
                                    isPlanViewerOpen={showPlanViewer}
                                    isPlannerStreaming={isPlanStreaming}
                                    currentViewingPlanContent={planContent}
                                    projectTitle={projectTitle}
                                    onTerminalLog={handleTerminalLog}
                                    onWorkflowComplete={handleWorkflowComplete}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
