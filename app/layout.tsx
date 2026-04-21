import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/Providers'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'AjoVault — Crypto-powered Ajo/Susu group savings',
  description:
    'Your group savings. Protected by crypto. Trusted by all. AjoVault is a modern Ajo/Susu platform for Africa.',
  keywords: ['ajo', 'susu', 'esusu', 'group savings', 'crypto', 'USDT', 'Nigeria', 'Ghana'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-ink-900 text-ink-50 font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
