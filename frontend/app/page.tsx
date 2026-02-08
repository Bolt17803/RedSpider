'use client'

import { useState, useEffect } from 'react'
import HomeLanding from '@/components/HomeLanding'
import Workspace from '@/components/Workspace'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [isProjectStarted, setIsProjectStarted] = useState(false)
  const [projectTitle, setProjectTitle] = useState('')
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null)
  const [shouldLoadHistory, setShouldLoadHistory] = useState(false)

  // Auto-resume if session exists and is valid
  useEffect(() => {
    const validateSession = async () => {
      const savedThreadId = localStorage.getItem('thread_id')
      if (!savedThreadId) return

      try {
        const res = await fetch(`${API_BASE_URL}/projects-history`)
        if (res.ok) {
          const data = await res.json()
          const projects = data.projects || []
          const project = projects.find((p: any) => p.id === savedThreadId)

          if (project) {
            setProjectTitle(project.title)
            setCurrentThreadId(savedThreadId)
            setShouldLoadHistory(true)
            setIsProjectStarted(true)
          } else {
            console.warn('Found invalid thread_id in localStorage, clearing:', savedThreadId)
            localStorage.removeItem('thread_id')
            setIsProjectStarted(false)
          }
        }
      } catch (error) {
        console.error("Failed to validate session:", error)
        // Only auto-resume if we can't reach backend? Safer to not resume if unsure.
      }
    }

    validateSession()
  }, [])

  const handleCreateProject = async (name: string) => {
    try {
      // 1. Generate a new Thread ID locally (do not start workflow yet)
      const threadId = crypto.randomUUID()

      // 2. Register project in CSV
      await fetch(`${API_BASE_URL}/create-project`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: name, thread_id: threadId })
      })

      // 3. Save to local storage and enter workspace
      localStorage.setItem('thread_id', threadId)
      setProjectTitle(name)
      setCurrentThreadId(threadId)
      setShouldLoadHistory(false) // Do NOT load history for new project
      setIsProjectStarted(true)

    } catch (error) {
      console.error("Error creating project:", error)
      alert("Failed to create project")
    }
  }

  const handleOpenProject = (id: string, title: string) => {
    localStorage.setItem('thread_id', id)
    setProjectTitle(title)
    setCurrentThreadId(id)
    setShouldLoadHistory(true) // Load history for existing project
    setIsProjectStarted(true)
  }

  return (
    <>
      {!isProjectStarted ? (
        <HomeLanding
          onStart={handleCreateProject}
          onOpen={handleOpenProject}
        />
      ) : (
        <Workspace
          onHome={() => setIsProjectStarted(false)}
          projectTitle={projectTitle}
          initialThreadId={currentThreadId}
          shouldLoadHistory={shouldLoadHistory}
        />
      )}
    </>
  )
}
