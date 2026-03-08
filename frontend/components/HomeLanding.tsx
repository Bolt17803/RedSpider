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

    // Handle New Project submission
    const handleStartProject = () => {
        if (!projectName.trim()) return
        onStart(projectName)
        setShowNameModal(false)
    }

    return (
        <main className="h-screen overflow-hidden bg-obsidian flex flex-col items-center justify-center relative font-sans">
            {/* Minimalist background grid for texture (optional luxurious touch) */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.03]"
                style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '32px 32px' }}>
            </div>

            <div className="flex flex-col items-center z-10 p-8 text-center max-w-2xl">
                <h1 className="text-7xl md:text-8xl font-thin tracking-widest text-platinum mb-4">
                    TARANTULA
                </h1>
                <div className="w-12 h-[1px] bg-white/20 mb-8 rounded-full"></div>
                <p className="text-lg md:text-xl text-platinum-muted font-light tracking-[0.2em] uppercase mb-14">
                    AI Agent Workflow System
                </p>

                <div className="flex flex-col sm:flex-row gap-5 w-full max-w-md justify-center">
                    <button
                        className="px-8 py-3.5 text-sm uppercase tracking-widest font-medium text-platinum flex-1 border border-white/10 hover:border-white/30 rounded-full hover:bg-white/5 transition-all duration-500"
                        onClick={handleOpenHistory}
                        disabled={isLoadingDetails}
                    >
                        {isLoadingDetails ? 'Loading...' : 'Open Project'}
                    </button>
                    <button
                        onClick={() => setShowNameModal(true)}
                        className="px-8 py-3.5 text-sm uppercase tracking-widest font-medium text-obsidian bg-platinum flex-1 rounded-full hover:bg-white transition-all duration-500 hover:shadow-[0_0_20px_rgba(255,255,255,0.3)]"
                    >
                        New Project
                    </button>
                </div>

                <p className="mt-16 text-xs text-white/20 font-mono tracking-widest">
                    V1.0.0 — LOCAL
                </p>
            </div>

            {/* Name Input Modal */}
            {showNameModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-obsidian/80 backdrop-blur-md transition-opacity">
                    <div className="bg-carbon border border-white/5 p-10 rounded-2xl w-full max-w-md shadow-2xl relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                        <h3 className="text-xl font-light tracking-wide text-platinum mb-8 text-center">INITIALIZE PROJECT</h3>
                        <input
                            type="text"
                            value={projectName}
                            onChange={(e) => setProjectName(e.target.value)}
                            placeholder="Enter project designation..."
                            className="w-full bg-obsidian border-b border-white/10 px-4 py-3 text-center text-platinum placeholder-white/20 focus:outline-none focus:border-white/50 transition-colors mb-8 font-light tracking-wide"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && handleStartProject()}
                        />
                        <div className="flex gap-4 justify-center">
                            <button
                                onClick={() => setShowNameModal(false)}
                                className="px-6 py-2.5 text-xs tracking-widest uppercase text-white/40 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartProject}
                                disabled={!projectName.trim()}
                                className="px-8 py-2.5 text-xs tracking-widest uppercase bg-platinum text-obsidian font-medium rounded-full hover:bg-white disabled:opacity-20 transition-all"
                            >
                                Launch
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* History Modal */}
            {showHistoryModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-obsidian/80 backdrop-blur-md transition-opacity">
                    <div className="bg-carbon border border-white/5 p-10 rounded-2xl w-full max-w-md shadow-2xl max-h-[80vh] flex flex-col relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                        <div className="flex justify-between items-center mb-8">
                            <h3 className="text-xl font-light tracking-wide text-platinum">SAVED PROJECTS</h3>
                            <button onClick={() => setShowHistoryModal(false)} className="text-white/20 hover:text-white transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="overflow-y-auto flex-1 min-h-0 space-y-1 pr-2 custom-scrollbar">
                            {projects.length === 0 ? (
                                <p className="text-white/20 text-center py-12 font-light tracking-wide text-sm">No archives found.</p>
                            ) : (
                                projects.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => onOpen(p.id, p.title)}
                                        className="w-full text-left px-5 py-4 rounded-xl hover:bg-white/[0.03] transition-colors group flex justify-between items-center"
                                    >
                                        <div className="font-light tracking-wide text-platinum/80 group-hover:text-white transition-colors truncate">
                                            {p.title}
                                        </div>
                                        <div className="text-[10px] text-white/20 font-mono tracking-widest">
                                            {p.id.substring(0, 8)}
                                        </div>
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
