'use client'

import { useState } from 'react'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface HomeLandingProps {
    onStart: (projectName: string) => void
    onOpen: (projectId: string, projectTitle: string) => void
}

interface Project {
    title: string
    id: string
}

export default function HomeLanding({ onStart, onOpen }: HomeLandingProps) {
    const [showNameModal, setShowNameModal] = useState(false)
    const [showHistoryModal, setShowHistoryModal] = useState(false)
    const [projectName, setProjectName] = useState('')
    const [projects, setProjects] = useState<Project[]>([])
    const [isLoadingDetails, setIsLoadingDetails] = useState(false)

    // Handle fetching project history
    const handleOpenHistory = async () => {
        setIsLoadingDetails(true)
        try {
            const response = await fetch(`${API_BASE_URL}/projects-history`)
            if (response.ok) {
                const data = await response.json()
                setProjects(data.projects || [])
                setShowHistoryModal(true)
            }
        } catch (error) {
            console.error("Failed to fetch history", error)
        } finally {
            setIsLoadingDetails(false)
        }
    }

    const handleStartProject = () => {
        if (!projectName.trim()) return
        onStart(projectName)
        setShowNameModal(false)
    }

    return (
        <main className="h-screen overflow-hidden bg-pure-black flex flex-col items-center justify-center relative font-sans text-text-primary px-6">
            
            {/* Minimalist Ambient Spotlight Background */}
            <div className="absolute inset-0 w-full h-full pointer-events-none overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(99,102,241,0.08)_0%,transparent_70%)] opacity-80 z-0"></div>
                
                {/* Aurora Mesh Glows */}
                <div className="absolute top-[-10%] left-[20%] w-[50vw] h-[50vh] bg-accent-indigo/10 blur-[100px] rounded-full mix-blend-screen animate-mesh-1 z-0"></div>
                <div className="absolute top-[10%] right-[10%] w-[40vw] h-[40vh] bg-accent-violet/10 blur-[100px] rounded-full mix-blend-screen animate-mesh-2 z-0"></div>
                <div className="absolute bottom-[20%] left-[30%] w-[60vw] h-[30vh] bg-accent-silver/5 blur-[120px] rounded-full mix-blend-screen animate-mesh-3 z-0"></div>

                {/* Subtle Grid overlay for texture */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_100%_100%_at_50%_0%,#000_10%,transparent_80%)] z-0"></div>
            </div>

            <div className="flex flex-col items-center z-10 w-full max-w-3xl text-center">
                
                {/* Brand / Headline Section */}
                <div className="mb-4 animate-fade-in-up stagger-1">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 backdrop-blur-md mb-8">
                        <span className="w-2 h-2 rounded-full bg-accent-indigo animate-pulse-subtle"></span>
                        <span className="text-xs font-medium tracking-wide text-text-secondary uppercase">Platform V1.0</span>
                    </div>
                </div>

                <h1 className="text-5xl md:text-7xl font-heading font-medium tracking-tight text-transparent bg-clip-text bg-gradient-metallic mb-6 animate-fade-in-up stagger-2">
                    Build Faster with Tarantula
                </h1>
                
                <p className="text-lg md:text-xl text-text-secondary font-sans leading-relaxed max-w-xl mx-auto mb-12 animate-fade-in-up stagger-3">
                    The enterprise-grade autonomous coding platform. Ship MVPs from natural language to production code with unprecedented velocity.
                </p>

                {/* Primary CTA Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 w-full justify-center items-center animate-fade-in-up stagger-4">
                    <button
                        onClick={() => setShowNameModal(true)}
                        className="w-full sm:w-auto px-8 py-3.5 text-sm font-medium text-pure-black bg-text-primary rounded-lg hover:bg-white/90 transition-all duration-300 shadow-[0_0_24px_rgba(255,255,255,0.1)] hover:shadow-[0_0_32px_rgba(255,255,255,0.2)] transform hover:scale-[0.98]"
                    >
                        Start New Project
                    </button>
                    <button
                        onClick={handleOpenHistory}
                        disabled={isLoadingDetails}
                        className="w-full sm:w-auto px-8 py-3.5 text-sm font-medium text-text-primary bg-charcoal-elevated border border-border-subtle rounded-lg hover:border-border-focus hover:bg-white/[0.03] transition-all duration-300"
                    >
                        {isLoadingDetails ? 'Loading...' : 'Open Workspace'}
                    </button>
                </div>
            </div>

            {/* Name Input Modal - High-End Aesthetic */}
            {showNameModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-pure-black/80 backdrop-blur-sm animate-fade-in-up">
                    <div className="surface-panel w-full max-w-md rounded-xl p-8 transform transition-all">
                        <h3 className="text-xl font-heading font-medium text-text-primary mb-2">Initialize Project</h3>
                        <p className="text-sm text-text-secondary mb-6">Enter a designation for your new workspace.</p>
                        
                        <div className="relative mb-8 group">
                            <input
                                type="text"
                                value={projectName}
                                onChange={(e) => setProjectName(e.target.value)}
                                placeholder="e.g., e-commerce-mvp"
                                className="w-full bg-charcoal-base border border-border-subtle rounded-lg px-4 py-3 text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-indigo focus:ring-1 focus:ring-accent-indigo transition-all font-sans text-base"
                                autoFocus
                                onKeyDown={(e) => e.key === 'Enter' && handleStartProject()}
                            />
                        </div>
                        
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowNameModal(false)}
                                className="px-5 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary rounded-lg hover:bg-white/5 transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartProject}
                                disabled={!projectName.trim()}
                                className="px-5 py-2.5 text-sm font-medium bg-text-primary text-pure-black rounded-lg disabled:opacity-50 hover:bg-white/90 transition-all"
                            >
                                Continue
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* History Modal - High-End Aesthetic */}
            {showHistoryModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-pure-black/80 backdrop-blur-sm animate-fade-in-up">
                    <div className="surface-panel w-full max-w-2xl rounded-xl max-h-[80vh] flex flex-col shadow-2xl">
                        
                        <div className="flex justify-between items-center px-8 py-6 border-b border-border-subtle">
                            <div>
                                <h3 className="text-lg font-heading font-medium text-text-primary">Recent Workspaces</h3>
                                <p className="text-sm text-text-tertiary mt-1">Select a workspace to resume execution</p>
                            </div>
                            <button onClick={() => setShowHistoryModal(false)} className="p-2 text-text-secondary hover:text-text-primary hover:bg-white/5 rounded-md transition-all">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="overflow-y-auto flex-1 p-4 space-y-2 custom-scrollbar">
                            {projects.length === 0 ? (
                                <div className="py-20 text-center flex flex-col items-center">
                                    <div className="w-12 h-12 rounded-full bg-white/5 mb-4 flex items-center justify-center">
                                        <svg className="w-6 h-6 text-text-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                                        </svg>
                                    </div>
                                    <p className="text-text-secondary text-sm font-medium">No workspaces found</p>
                                    <p className="text-text-tertiary text-xs mt-1">Start a new project to see it here.</p>
                                </div>
                            ) : (
                                projects.map((p, i) => (
                                    <button
                                        key={p.id}
                                        onClick={() => onOpen(p.id, p.title)}
                                        className="surface-panel-interactive w-full text-left px-5 py-4 rounded-lg flex items-center justify-between group"
                                        style={{ animationDelay: `${(i % 5) * 50}ms` }}
                                    >
                                        <div className="flex flex-col">
                                            <span className="font-heading font-medium text-text-primary group-hover:text-accent-indigo transition-colors">{p.title}</span>
                                            <span className="text-xs font-mono text-text-tertiary mt-1">ID: {p.id.substring(0, 8)}</span>
                                        </div>
                                        <svg className="w-5 h-5 text-text-tertiary group-hover:text-accent-indigo transition-colors transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5l7 7-7 7" />
                                        </svg>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}
