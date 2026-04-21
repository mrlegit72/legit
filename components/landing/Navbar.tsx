'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Menu, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/utils'

const links = [
  { label: 'How it works', href: '#how' },
  { label: 'Features', href: '#features' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
]

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    onScroll()
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-50 transition-all duration-300',
        scrolled
          ? 'bg-ink-900/80 backdrop-blur-xl border-b border-ink-700/60'
          : 'bg-transparent'
      )}
    >
      <nav className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Logo />
          <div className="hidden md:flex items-center gap-8">
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="text-sm text-ink-200 hover:text-gold transition"
              >
                {l.label}
              </a>
            ))}
          </div>
          <div className="hidden md:flex items-center gap-3">
            <Link href="/auth/login" className="text-sm text-ink-200 hover:text-gold transition">
              Login
            </Link>
            <Link href="/auth/register" className="btn-gold text-sm px-4 py-2">
              Get Started
            </Link>
          </div>
          <button
            className="md:hidden text-ink-100 p-2"
            aria-label="Toggle menu"
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="md:hidden border-t border-ink-700 bg-ink-900"
          >
            <div className="px-4 py-4 space-y-2">
              {links.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  className="block py-2 text-ink-200 hover:text-gold"
                  onClick={() => setOpen(false)}
                >
                  {l.label}
                </a>
              ))}
              <Link href="/auth/login" className="btn-ghost w-full mt-2">
                Login
              </Link>
              <Link href="/auth/register" className="btn-gold w-full">
                Get Started
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
