'use client'

import { useState } from 'react'
import WorkflowGraph from '@/components/WorkflowGraph'
import ChatInterface from '@/components/ChatInterface'
import PlanViewer from '@/components/PlanViewer'

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

    return (
        <div className="flex h-screen bg-[#111111] text-white overflow-hidden">
            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <header className="h-14 border-b border-gray-800 flex items-center justify-between px-6 bg-[#161616]">
                    <div className="flex items-center gap-4">
                        <h1 className="text-sm font-medium text-gray-400">RedSpider Agent</h1>
                        {projectTitle && (
                            <>
                                <span className="text-gray-600">/</span>
                                <span className="text-sm font-medium text-white">{projectTitle}</span>
                            </>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={onHome}
                            className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-md transition-colors text-gray-300"
                        >
                            Back to Home
                        </button>
                    </div>
                </header>

                {/* Main Content */}
                <div className="flex-1 flex gap-6 px-8 py-6 min-h-0">
                    {/* Graph Panel - Fixed width */}
                    <div className="w-[10%] flex-shrink-0 flex flex-col">
                        <h2 className="text-xs font-medium text-warm-beige/60 uppercase tracking-wider mb-5">
                            Workflow Status
                        </h2>
                        <div className="flex-1 min-h-0">
                            <WorkflowGraph activeNode={activeNode} />
                        </div>
                    </div>

                    {/* Plan Viewer Panel - Animated slide in/out */}
                    <div
                        className={`flex-shrink-0 flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${showPlanViewer ? 'w-[35%] opacity-100' : 'w-0 opacity-0'
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

                    {/* Chat Panel - Flexible, shrinks when plan viewer is open */}
                    <div className={`min-h-0 flex flex-col transition-all duration-300 ease-in-out ${showPlanViewer ? 'flex-1' : 'flex-1'
                        }`}>
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
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
