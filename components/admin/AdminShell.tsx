'use client'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Plug,
  Globe2,
  Users,
  Boxes,
  Banknote,
  Settings as SettingsIcon,
  FileClock,
  ShieldCheck,
  Menu,
  X,
  ArrowLeft,
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { cn, initials } from '@/lib/utils'

const nav = [
  { href: '/admin', label: 'Overview', icon: LayoutDashboard },
  { href: '/admin/providers', label: 'Providers', icon: Plug },
  { href: '/admin/countries', label: 'Countries', icon: Globe2 },
  { href: '/admin/users', label: 'Users', icon: Users },
  { href: '/admin/groups', label: 'Groups', icon: Boxes },
  { href: '/admin/withdrawals', label: 'Withdrawals', icon: Banknote },
  { href: '/admin/treasury', label: 'Treasury', icon: ShieldCheck },
  { href: '/admin/settings', label: 'Settings', icon: SettingsIcon },
  { href: '/admin/audit', label: 'Audit log', icon: FileClock },
]

export function AdminShell({
  children,
  admin,
}: {
  children: React.ReactNode
  admin: { id: string; name: string; email: string; image: string | null }
}) {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-ink-900">
      <aside className="hidden lg:flex w-64 flex-col fixed inset-y-0 left-0 border-r border-ink-700 bg-ink-950">
        <div className="h-16 flex items-center px-6 border-b border-ink-700 gap-2">
          <Logo size="sm" />
          <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-gold/15 text-gold border border-gold/30">
            Admin
          </span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active =
              item.href === '/admin'
                ? pathname === '/admin'
                : pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition',
                  active
                    ? 'bg-gold/10 text-gold border border-gold/20'
                    : 'text-ink-200 hover:bg-ink-800 hover:text-ink-50 border border-transparent'
                )}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t border-ink-700">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-ink-300 hover:text-gold"
          >
            <ArrowLeft size={14} /> Back to app
          </Link>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="lg:hidden fixed inset-x-0 top-0 z-40 h-16 bg-ink-950 border-b border-ink-700 flex items-center justify-between px-4">
        <button className="p-2 text-ink-100" onClick={() => setOpen(!open)}>
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
        <Logo size="sm" />
        <div className="w-9" />
      </div>
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 bg-black/60" onClick={() => setOpen(false)}>
          <aside
            className="absolute inset-y-0 left-0 w-72 bg-ink-950 border-r border-ink-700 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="h-16 flex items-center justify-between px-4 border-b border-ink-700">
              <Logo size="sm" />
              <button className="p-2" onClick={() => setOpen(false)}>
                <X size={20} />
              </button>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {nav.map((item) => {
                const active =
                  item.href === '/admin'
                    ? pathname === '/admin'
                    : pathname.startsWith(item.href)
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition',
                      active
                        ? 'bg-gold/10 text-gold border border-gold/20'
                        : 'text-ink-200 hover:bg-ink-800'
                    )}
                  >
                    <item.icon size={16} /> {item.label}
                  </Link>
                )
              })}
            </nav>
          </aside>
        </div>
      )}

      <div className="flex-1 lg:ml-64 pt-16 lg:pt-0">
        <header className="hidden lg:flex sticky top-0 z-30 h-16 items-center justify-between border-b border-ink-700 bg-ink-950/80 backdrop-blur px-6">
          <div className="text-sm text-ink-300">
            <span className="text-ink-100 font-medium">Admin panel</span> — signed in as {admin.email}
          </div>
          <div className="flex items-center gap-2">
            {admin.image ? (
              <Image
                src={admin.image}
                alt={admin.name}
                width={32}
                height={32}
                className="h-8 w-8 rounded-full bg-ink-700"
                unoptimized
              />
            ) : (
              <span className="h-8 w-8 rounded-full bg-gold text-ink-950 text-xs font-bold flex items-center justify-center">
                {initials(admin.name)}
              </span>
            )}
          </div>
        </header>
        <main className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">{children}</main>
      </div>
    </div>
  )
}
