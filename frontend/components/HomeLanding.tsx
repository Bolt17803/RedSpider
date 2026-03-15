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
            {/* Animated Ambient Background - Luxurious Aurora/Orbs effect */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-electric-blue/5 blur-[120px] animate-float-slow mix-blend-screen"></div>
                <div className="absolute bottom-[-20%] right-[-10%] w-[60vw] h-[60vw] rounded-full bg-gold-accent/5 blur-[150px] animate-float-slower mix-blend-screen"></div>
                <div className="absolute top-[20%] right-[10%] w-[30vw] h-[30vw] rounded-full bg-electric-cyan/5 blur-[100px] animate-float-slow mix-blend-screen" style={{ animationDelay: '2s' }}></div>
                <div className="absolute inset-0 bg-obsidian/40 backdrop-blur-[50px]"></div>
                
                {/* Subtle refined grid */}
                <div className="absolute inset-0"
                    style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.03) 1px, transparent 0)', backgroundSize: '48px 48px' }}>
                </div>
            </div>

            <div className="flex flex-col items-center z-10 p-8 text-center max-w-2xl">
                <div className="relative mb-6">
                    <h1 className="text-7xl md:text-8xl font-thin tracking-[0.25em] text-transparent bg-clip-text bg-gradient-to-b from-white via-platinum to-platinum-dark drop-shadow-2xl">
                        TARANTULA
                    </h1>
                    <div className="absolute inset-0 bg-gradient-to-tr from-gold-accent/0 via-gold-accent/10 to-transparent blur-2xl z-[-1]"></div>
                </div>
                <div className="w-16 h-[1px] bg-gradient-to-r from-transparent via-gold-accent/40 to-transparent mb-10 rounded-full"></div>
                <p className="text-lg md:text-xl text-platinum-muted font-light tracking-[0.3em] uppercase mb-16 text-glow">
                    AI Agent Workflow System
                </p>

                <div className="flex flex-col sm:flex-row gap-6 w-full max-w-lg justify-center relative">
                    <button
                        className="px-8 py-4 text-sm uppercase tracking-[0.2em] font-medium text-platinum flex-1 border border-white/10 rounded-full hover:bg-white/[0.03] hover:border-gold-accent/40 transition-all duration-500 shadow-[0_0_0_rgba(212,175,55,0)] hover:shadow-[0_0_20px_rgba(212,175,55,0.15)] relative overflow-hidden group"
                        onClick={handleOpenHistory}
                        disabled={isLoadingDetails}
                    >
                        <span className="relative z-10">{isLoadingDetails ? 'Loading...' : 'Open Project'}</span>
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-gold-accent/5 to-transparent -translate-x-full group-hover:animate-[aurora_3s_linear_infinite] pointer-events-none"></div>
                    </button>
                    <button
                        onClick={() => setShowNameModal(true)}
                        className="px-8 py-4 text-sm uppercase tracking-[0.2em] font-medium text-obsidian bg-gradient-to-br from-platinum to-platinum-muted flex-1 rounded-full hover:from-white hover:to-platinum transition-all duration-500 hover:shadow-[0_0_30px_rgba(255,255,255,0.4)] transform hover:-translate-y-0.5"
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
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-obsidian/90 backdrop-blur-xl transition-all duration-500">
                    <div className="glass-premium p-10 rounded-2xl w-full max-w-md relative overflow-hidden transform transition-all scale-100 opacity-100 animate-in fade-in zoom-in-95 duration-300">
                        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-gold-accent/40 to-transparent"></div>
                        <h3 className="text-xl font-light tracking-[0.2em] text-platinum mb-8 text-center drop-shadow-md">INITIALIZE PROJECT</h3>
                        <div className="relative mb-10">
                            <input
                                type="text"
                                value={projectName}
                                onChange={(e) => setProjectName(e.target.value)}
                                placeholder="Enter project designation..."
                                className="w-full bg-transparent border-b border-white/10 px-4 py-3 text-center text-platinum placeholder-white/20 focus:outline-none focus:border-gold-accent/50 transition-colors font-light tracking-wide text-lg relative z-10"
                                autoFocus
                                onKeyDown={(e) => e.key === 'Enter' && handleStartProject()}
                            />
                            <div className="absolute bottom-0 left-0 h-[1px] bg-gradient-to-r from-transparent via-gold-accent to-transparent w-full scale-x-0 opacity-0 transition-all duration-500 peer-focus:scale-x-100 peer-focus:opacity-100"></div>
                        </div>
                        <div className="flex gap-5 justify-center">
                            <button
                                onClick={() => setShowNameModal(false)}
                                className="px-6 py-3 text-xs tracking-[0.2em] uppercase text-white/40 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartProject}
                                disabled={!projectName.trim()}
                                className="px-10 py-3 text-xs tracking-[0.2em] uppercase bg-gradient-to-r from-platinum to-platinum-muted text-obsidian font-medium rounded-full hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] disabled:opacity-20 disabled:shadow-none transition-all duration-300 transform hover:-translate-y-0.5 disabled:transform-none"
                            >
                                Launch
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* History Modal */}
            {showHistoryModal && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-obsidian/90 backdrop-blur-xl transition-all duration-500">
                    <div className="glass-premium p-10 rounded-2xl w-full max-w-xl shadow-[0_20px_60px_rgba(0,0,0,0.8)] max-h-[85vh] flex flex-col relative overflow-hidden animate-in fade-in zoom-in-95 duration-300">
                        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-electric-blue/40 to-transparent"></div>
                        <div className="flex justify-between items-center mb-8 border-b border-white/5 pb-6">
                            <h3 className="text-xl font-light tracking-[0.2em] text-platinum drop-shadow-md">SAVED PROJECTS</h3>
                            <button onClick={() => setShowHistoryModal(false)} className="text-white/30 hover:text-white hover:rotate-90 transition-all duration-300">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="overflow-y-auto flex-1 min-h-0 space-y-2 pr-3 custom-scrollbar">
                            {projects.length === 0 ? (
                                <p className="text-white/30 text-center py-16 font-light tracking-[0.1em] text-sm">No archives found.</p>
                            ) : (
                                projects.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => onOpen(p.id, p.title)}
                                        className="w-full text-left px-6 py-5 rounded-xl border border-white/[0.03] hover:border-electric-blue/30 hover:bg-white/[0.04] transition-all duration-300 group flex justify-between items-center hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] relative overflow-hidden"
                                    >
                                        <div className="font-light tracking-wide text-platinum/90 group-hover:text-white transition-colors truncate text-lg">
                                            {p.title}
                                        </div>
                                        <div className="text-[11px] text-white/30 font-mono tracking-[0.15em] bg-black/40 px-3 py-1 rounded-full group-hover:text-electric-blue/80 transition-colors">
                                            {p.id.substring(0, 8)}
                                        </div>
                                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-electric-blue/5 to-transparent -translate-x-full group-hover:animate-[aurora_2s_linear_infinite] pointer-events-none"></div>
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
