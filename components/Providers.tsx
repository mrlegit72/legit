'use client'

import { SessionProvider } from 'next-auth/react'
import { Toaster } from 'react-hot-toast'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1A1A1A',
            color: '#F5F5F5',
            border: '1px solid #2F2F2F',
          },
          success: {
            iconTheme: {
              primary: '#10B981',
              secondary: '#0A0A0A',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#0A0A0A',
            },
          },
        }}
      />
    </SessionProvider>
  )
}
