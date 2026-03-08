'use client'

import { useState } from 'react'
import WorkflowGraph from '@/components/WorkflowGraph'
import ChatInterface from '@/components/ChatInterface'
import PlanViewer from '@/components/PlanViewer'
import TerminalOutput from '@/components/TerminalOutput'

interface WorkspaceProps {
    onHome: () => void
    projectTitle?: string
    initialThreadId?: string | null
    shouldLoadHistory?: boolean
}

export default function Workspace({ onHome, projectTitle, initialThreadId, shouldLoadHistory }: WorkspaceProps) {
    const [activeNode, setActiveNode] = useState<string | null>('architect_agent')
    const [threadId, setThreadId] = useState<string | null>(initialThreadId || null)
    const [showPlanViewer, setShowPlanViewer] = useState(false)
    const [planContent, setPlanContent] = useState('')
    const [isPlanStreaming, setIsPlanStreaming] = useState(false)
    const [terminalLogs, setTerminalLogs] = useState<string[]>([])
    const [showTerminal, setShowTerminal] = useState(false)

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

    return (
        <div className="flex h-screen bg-obsidian text-platinum font-sans overflow-hidden">
            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <header className="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-obsidian/80 backdrop-blur-md z-10">
                    <div className="flex items-center gap-4">
                        <h1 className="text-sm font-light tracking-widest text-platinum-muted uppercase text-[11px]">Tarantula Workspace</h1>
                        {projectTitle && (
                            <>
                                <span className="text-white/10">|</span>
                                <span className="text-sm font-normal tracking-wide text-platinum">{projectTitle}</span>
                            </>
                        )}
                    </div>
                    <div className="flex items-center gap-4">
                        {/* Terminal toggle button */}
                        <button
                            onClick={() => setShowTerminal(!showTerminal)}
                            className={`flex items-center gap-2 text-xs px-4 py-2 rounded-full transition-all border ${showTerminal
                                ? 'bg-white/10 border-white/20 text-white shadow-[0_0_10px_rgba(255,255,255,0.1)]'
                                : 'bg-transparent border-white/5 hover:bg-white/5 hover:border-white/10 text-platinum-muted'
                                }`}
                            title="Toggle Terminal"
                        >
                            {/* Terminal icon */}
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <span className="uppercase tracking-widest text-[10px] font-medium">Terminal</span>
                            {terminalLogs.length > 0 && !showTerminal && (
                                <span className="ml-1 w-4 h-4 rounded-full bg-white text-[9px] font-bold text-obsidian flex items-center justify-center">
                                    {terminalLogs.length > 9 ? '9+' : terminalLogs.length}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={onHome}
                            className="text-[10px] uppercase tracking-widest px-4 py-2 bg-transparent border border-transparent hover:border-white/10 hover:bg-white/5 rounded-full transition-all text-platinum-muted hover:text-white"
                        >
                            End Session
                        </button>
                    </div>
                </header>

                {/* Agent Progress Banner */}
                {activeNode && !['architect_agent', 'architect_review'].includes(activeNode) && (
                    <div className="h-10 border-b border-white/5 flex items-center px-8 bg-carbon-light/50">
                        <div className="flex items-center gap-4 max-w-4xl mx-auto w-full">
                            <div className="relative flex h-1.5 w-1.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-40"></span>
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]"></span>
                            </div>
                            <span className="text-[11px] uppercase tracking-widest font-medium text-platinum flex space-x-2">
                                <span className="text-white/40">[{activeNode.split('_')[0]}]</span>
                                <span>
                                    {activeNode.includes('init') ? 'Initializing system...' :
                                        activeNode.includes('planner') ? 'Architecting blueprint...' :
                                            activeNode.includes('coder') ? 'Synthesizing implementation...' :
                                                activeNode.includes('validation') ? 'Verifying codebase integrity...' :
                                                    activeNode.includes('tester') ? 'Executing test suite...' :
                                                        activeNode.includes('human') ? 'Awaiting human authorization...' :
                                                            'Processing...'}
                                </span>
                            </span>
                        </div>
                    </div>
                )}

                {/* Main Content */}
                <div className="flex-1 flex gap-4 px-6 py-6 min-h-0 bg-obsidian">
                    {/* Graph Panel - Fixed width */}
                    <div className="w-[10%] flex-shrink-0 flex flex-col pt-2">
                        <h2 className="text-[10px] font-medium text-white/30 uppercase tracking-[0.2em] mb-6 px-2">
                            Topology
                        </h2>
                        <div className="flex-1 min-h-0">
                            <WorkflowGraph activeNode={activeNode} />
                        </div>
                    </div>

                    {/* Plan Viewer Panel - slide in/out */}
                    <div
                        className={`flex-shrink-0 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${showPlanViewer ? 'w-[30%] opacity-100' : 'w-0 opacity-0'
                            }`}
                    >
                        {showPlanViewer && (
                            <div className="flex-1 min-h-0">
                                <PlanViewer
                                    content={planContent}
                                    isStreaming={isPlanStreaming}
                                    onClose={handleClosePlanViewer}
                                />
                            </div>
                        )}
                    </div>

                    {/* Terminal Panel - slide in/out (like plan viewer) */}
                    <div
                        className={`flex-shrink-0 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${showTerminal ? 'w-[28%] opacity-100' : 'w-0 opacity-0'
                            }`}
                    >
                        {showTerminal && (
                            <div className="flex-1 min-h-0">
                                <TerminalOutput
                                    logs={terminalLogs}
                                    onClose={() => setShowTerminal(false)}
                                />
                            </div>
                        )}
                    </div>

                    {/* Chat Panel - Flexible */}
                    <div className="flex-1 min-h-0 flex flex-col">
                        <div className="glass-strong rounded-xl h-full flex flex-col overflow-hidden">
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
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
