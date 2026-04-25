'use client'

import { useState, useEffect } from 'react'

interface FileNode {
  name: string
  type: 'file' | 'directory'
  path: string
  children?: FileNode[]
}

interface CodeViewerProps {
  projectId: string
  onClose: () => void
  isExpanded?: boolean
  onToggleExpand?: () => void
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Simple File Tree Component
function FileTree({ data, onSelectFile, currentFile }: { data: FileNode[], onSelectFile: (path: string) => void, currentFile: string | null }) {
  if (!data || data.length === 0) {
    return <div className="p-4 text-xs text-text-tertiary">Workspace is empty</div>
  }

  const renderNode = (node: FileNode, depth = 0) => {
    const isFile = node.type === 'file'
    const isSelected = currentFile === node.path

    if (!isFile) {
      return (
        <div key={node.path} className="w-full">
          <div 
            className="flex items-center py-1.5 px-2 text-text-secondary hover:bg-white/5 cursor-pointer transition-colors"
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
          >
            <svg className="w-4 h-4 mr-2 text-accent-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="text-xs font-medium truncate">{node.name}</span>
          </div>
          <div className="flex flex-col">
            {node.children?.map(child => renderNode(child, depth + 1))}
          </div>
        </div>
      )
    }

    return (
      <div 
        key={node.path}
        onClick={() => onSelectFile(node.path)}
        className={`flex items-center py-1.5 px-2 cursor-pointer transition-colors group
          ${isSelected ? 'bg-accent-indigo/10 text-accent-indigo' : 'text-text-secondary hover:bg-white/5'}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <svg className={`w-3.5 h-3.5 mr-2.5 ${isSelected ? 'text-accent-indigo' : 'text-text-tertiary group-hover:text-text-secondary'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
        <span className="text-xs truncate">{node.name}</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col overflow-y-auto w-full pb-4">
      {data.map(n => renderNode(n, 0))}
    </div>
  )
}

export default function CodeViewer({ projectId, onClose, isExpanded, onToggleExpand }: CodeViewerProps) {
  const [tree, setTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [isLoadingTree, setIsLoadingTree] = useState(true)
  const [isLoadingFile, setIsLoadingFile] = useState(false)

  // Fetch Tree
  const fetchTree = async () => {
    setIsLoadingTree(true)
    try {
      const res = await fetch(`${API_BASE_URL}/workspace/tree/${encodeURIComponent(projectId)}`)
      if (res.ok) {
        const data = await res.json()
        setTree(data.tree)
      }
    } catch (err) {
      console.error("Failed to load workspace tree", err)
    } finally {
      setIsLoadingTree(false)
    }
  }

  useEffect(() => {
    if (projectId) {
      fetchTree()
      // Auto-refresh the file tree every 5 seconds to show new files agent created
      const interval = setInterval(fetchTree, 5000)
      return () => clearInterval(interval)
    }
  }, [projectId])

  // Fetch File Content
  useEffect(() => {
    const fetchFile = async () => {
      if (!selectedFile) {
        setFileContent(null)
        return
      }
      setIsLoadingFile(true)
      try {
        const url = new URL(`${API_BASE_URL}/workspace/file/${encodeURIComponent(projectId)}`)
        url.searchParams.append('path', selectedFile)
        const res = await fetch(url.toString())
        if (res.ok) {
          const data = await res.json()
          setFileContent(data.content)
        } else {
          setFileContent(`// Error loading file: ${res.statusText}`)
        }
      } catch (err) {
        console.error("Failed to load file content", err)
        setFileContent('// Failed to connect to workspace server')
      } finally {
        setIsLoadingFile(false)
      }
    }
    fetchFile()
  }, [selectedFile, projectId])


  return (
    <div className="h-full flex flex-col bg-charcoal-base border border-border-subtle rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="h-10 flex items-center justify-between border-b border-border-subtle bg-charcoal-surface px-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-accent-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          <h2 className="text-xs font-heading font-medium tracking-wide text-text-primary">Workspace Code</h2>
        </div>
        <div className="flex items-center gap-2">
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              className="p-1 rounded-md text-text-tertiary hover:text-text-primary hover:bg-white/10 transition-colors"
              title={isExpanded ? "Collapse" : "Expand Fullscreen"}
            >
              {isExpanded ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 15v5M15 9V4M4 9h5M20 15h-5M9 15L4 20M15 9l5-5" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              )}
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded-md text-text-tertiary hover:text-text-primary hover:bg-white/10 transition-colors"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left Pane - File Tree */}
        <div className="w-48 flex-shrink-0 border-r border-border-subtle bg-pure-black/20 flex flex-col">
          <div className="h-8 flex items-center px-3 border-b border-white-[0.02] text-[10px] font-semibold tracking-wider text-text-tertiary uppercase">
             EXPLORER
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {isLoadingTree && tree.length === 0 ? (
              <div className="p-4 text-xs text-text-tertiary animate-pulse">Scanning...</div>
            ) : (
              <FileTree data={tree} onSelectFile={setSelectedFile} currentFile={selectedFile} />
            )}
          </div>
        </div>

        {/* Right Pane - Code Viewer */}
        <div className="flex-1 flex flex-col min-w-0 bg-charcoal-surface">
          {selectedFile ? (
            <>
              {/* Tab Header */}
              <div className="h-8 flex items-center bg-pure-black/40 border-b border-border-subtle px-3 flex-shrink-0">
                <span className="text-xs text-text-secondary font-mono tracking-tight truncate flex items-center gap-2">
                   {selectedFile.split('/').pop()}
                   <span className="text-[10px] text-text-tertiary ml-2 hidden sm:inline">{selectedFile}</span>
                </span>
              </div>
              <div className="flex-1 overflow-auto custom-scrollbar p-0 bg-[#0d0d0d]">
                {isLoadingFile ? (
                  <div className="flex items-center justify-center p-8 text-xs text-text-tertiary italic">
                    Loading contents...
                  </div>
                ) : (
                  <pre className="text-[13px] leading-relaxed font-mono text-text-primary p-4 m-0 overflow-x-auto min-h-full">
                    <code className="whitespace-pre">{fileContent || '\n'}</code>
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-text-tertiary w-full h-full p-4">
               <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-4 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
               </svg>
               <p className="text-xs">Select a file from the explorer</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
