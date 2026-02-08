import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'RedSpider - AI Agent Workflow',
  description: 'Multi-agent AI workflow system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

