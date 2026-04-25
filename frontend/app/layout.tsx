import type { Metadata } from 'next'
import { Outfit, Manrope, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const fontOutfit = Outfit({
  subsets: ['latin'],
  variable: '--font-outfit',
})

const fontManrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
})

const fontJetBrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
})

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
    <html lang="en" className={`${fontOutfit.variable} ${fontManrope.variable} ${fontJetBrains.variable}`}>
      <body className="font-sans antialiased text-text-primary bg-pure-black">
        {children}
      </body>
    </html>
  )
}
