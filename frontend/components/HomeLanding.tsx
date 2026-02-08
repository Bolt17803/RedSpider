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
        <main className="h-screen overflow-hidden bg-gradient-to-br from-warm-dark via-warm-gray to-warm-dark flex flex-col items-center justify-center relative">
            {/* Background decoration */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute -top-[20%] -right-[10%] w-[50%] h-[50%] bg-warm-amber/5 rounded-full blur-[100px]" />
                <div className="absolute bottom-[10%] -left-[10%] w-[40%] h-[40%] bg-warm-beige/5 rounded-full blur-[100px]" />
            </div>

            <div className="flex flex-col items-center z-10 p-8 text-center max-w-2xl">
                <h1 className="text-6xl md:text-8xl font-thin tracking-tighter text-warm-beige mb-4 shadow-sm drop-shadow-lg">
                    <span className="text-warm-amber font-medium">Tarantula</span>
                </h1>
                <p className="text-xl md:text-2xl text-warm-beige/60 font-light tracking-wide mb-12">
                    AI Agent Workflow System
                </p>

                <div className="flex flex-col sm:flex-row gap-6 w-full max-w-md justify-center">
                    <button
                        className="px-8 py-4 text-lg font-medium text-warm-beige/80 bg-warm-gray/20 border border-warm-gray/30 rounded-xl hover:bg-warm-gray/30 hover:text-warm-beige transition-all duration-300 w-full sm:w-auto"
                        onClick={handleOpenHistory}
                        disabled={isLoadingDetails}
                    >
                        {isLoadingDetails ? 'Loading...' : 'Open Project'}
                    </button>
                    <button
                        onClick={() => setShowNameModal(true)}
                        className="px-8 py-4 text-lg font-medium text-warm-dark bg-warm-amber hover:bg-warm-amber/90 rounded-xl shadow-lg shadow-warm-amber/20 hover:shadow-warm-amber/30 transition-all duration-300 transform hover:-translate-y-0.5 w-full sm:w-auto"
                    >
                        New Project
                    </button>
                </div>

                <p className="mt-8 text-sm text-warm-beige/30 font-light">
                    v1.0.0 • Local Environment
                </p>
            </div>

            {/* Name Input Modal */}
            {showNameModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div className="bg-warm-dark/95 border border-warm-gray/30 p-8 rounded-2xl w-full max-w-md shadow-2xl">
                        <h3 className="text-2xl font-light text-warm-beige mb-6">Name your project</h3>
                        <input
                            type="text"
                            value={projectName}
                            onChange={(e) => setProjectName(e.target.value)}
                            placeholder="My Awesome Project"
                            className="w-full bg-warm-gray/20 border border-warm-gray/40 rounded-xl px-4 py-3 text-warm-beige placeholder-warm-beige/30 focus:outline-none focus:border-warm-amber/50 mb-6"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && handleStartProject()}
                        />
                        <div className="flex gap-4 justify-end">
                            <button
                                onClick={() => setShowNameModal(false)}
                                className="px-6 py-2 text-sm text-warm-beige/60 hover:text-warm-beige transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartProject}
                                disabled={!projectName.trim()}
                                className="px-6 py-2 bg-warm-amber text-warm-dark font-medium rounded-lg hover:bg-warm-amber/90 disabled:opacity-50 transition-all"
                            >
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* History Modal */}
            {showHistoryModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <div className="bg-warm-dark/95 border border-warm-gray/30 p-8 rounded-2xl w-full max-w-md shadow-2xl max-h-[80vh] flex flex-col">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-2xl font-light text-warm-beige">Open Project</h3>
                            <button onClick={() => setShowHistoryModal(false)} className="text-warm-beige/40 hover:text-warm-beige">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="overflow-y-auto flex-1 min-h-0 space-y-2 pr-2 custom-scrollbar">
                            {projects.length === 0 ? (
                                <p className="text-warm-beige/40 text-center py-8">No saved projects found</p>
                            ) : (
                                projects.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => onOpen(p.id, p.title)}
                                        className="w-full text-left p-4 rounded-xl bg-warm-gray/10 hover:bg-warm-gray/20 border border-transparent hover:border-warm-amber/20 transition-all group"
                                    >
                                        <div className="font-medium text-warm-beige group-hover:text-warm-amber transition-colors truncate">
                                            {p.title}
                                        </div>
                                        <div className="text-xs text-warm-beige/30 font-mono mt-1 truncate">
                                            ID: {p.id.substring(0, 8)}...
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
