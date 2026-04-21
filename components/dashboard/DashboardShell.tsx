'use client'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { signOut } from 'next-auth/react'
import {
  LayoutDashboard,
  Users,
  PlusCircle,
  Receipt,
  Wallet,
  Settings,
  LogOut,
  Bell,
  Menu,
  X,
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { cn, formatUSDT, initials } from '@/lib/utils'

type Notification = {
  id: string
  title: string
  message: string
  createdAt: Date | string
}

const nav = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/dashboard/groups', label: 'My Groups', icon: Users },
  { href: '/dashboard/create', label: 'Create Group', icon: PlusCircle },
  { href: '/dashboard/transactions', label: 'Transactions', icon: Receipt },
  { href: '/dashboard/wallet', label: 'Wallet', icon: Wallet },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
]

export function DashboardShell({
  children,
  user,
  unreadNotifications,
}: {
  children: React.ReactNode
  user: { id: string; name: string; email: string; image: string | null; balance: number }
  unreadNotifications: Notification[]
}) {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-ink-900">
      {/* Sidebar (desktop) */}
      <aside className="hidden lg:flex w-64 flex-col fixed inset-y-0 left-0 border-r border-ink-700 bg-ink-950">
        <div className="h-16 flex items-center px-6 border-b border-ink-700">
          <Logo />
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active =
              item.href === '/dashboard'
                ? pathname === '/dashboard'
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
                <item.icon size={18} />
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t border-ink-700">
          <button
            onClick={() => signOut({ callbackUrl: '/' })}
            className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-ink-300 hover:text-red-400 hover:bg-ink-800 transition"
          >
            <LogOut size={18} /> Logout
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="lg:hidden fixed inset-x-0 top-0 z-40 h-16 bg-ink-950 border-b border-ink-700 flex items-center justify-between px-4">
        <button
          className="p-2 text-ink-100"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Menu"
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <Logo size="sm" />
        <div className="w-9" />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 bg-black/60"
          onClick={() => setMobileOpen(false)}
        >
          <aside
            className="absolute inset-y-0 left-0 w-72 bg-ink-950 border-r border-ink-700 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="h-16 flex items-center justify-between px-4 border-b border-ink-700">
              <Logo size="sm" />
              <button className="p-2" onClick={() => setMobileOpen(false)}>
                <X size={20} />
              </button>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {nav.map((item) => {
                const active =
                  item.href === '/dashboard'
                    ? pathname === '/dashboard'
                    : pathname.startsWith(item.href)
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition',
                      active
                        ? 'bg-gold/10 text-gold border border-gold/20'
                        : 'text-ink-200 hover:bg-ink-800'
                    )}
                  >
                    <item.icon size={18} />
                    {item.label}
                  </Link>
                )
              })}
            </nav>
            <div className="p-3 border-t border-ink-700">
              <button
                onClick={() => signOut({ callbackUrl: '/' })}
                className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-ink-300 hover:text-red-400"
              >
                <LogOut size={18} /> Logout
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 lg:ml-64 pt-16 lg:pt-0 pb-20 lg:pb-0">
        {/* Top bar (desktop) */}
        <header className="hidden lg:flex sticky top-0 z-30 h-16 items-center justify-end gap-4 border-b border-ink-700 bg-ink-950/80 backdrop-blur px-6">
          <div className="hidden sm:flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-800 px-3 py-1.5">
            <Wallet size={14} className="text-gold" />
            <span className="text-sm text-ink-200">Balance</span>
            <span className="text-sm font-semibold gold-text">
              {formatUSDT(user.balance)} USDT
            </span>
          </div>
          <div className="relative">
            <button
              onClick={() => setNotifOpen(!notifOpen)}
              className="relative h-10 w-10 rounded-xl border border-ink-700 bg-ink-800 flex items-center justify-center text-ink-200 hover:text-gold hover:border-gold/40"
            >
              <Bell size={16} />
              {unreadNotifications.length > 0 && (
                <span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 rounded-full bg-gold text-ink-950 text-[10px] font-bold flex items-center justify-center">
                  {unreadNotifications.length}
                </span>
              )}
            </button>
            {notifOpen && (
              <div className="absolute right-0 top-12 w-80 card p-2 shadow-xl z-50">
                <p className="px-3 py-2 text-xs text-ink-300 uppercase tracking-wide">
                  Notifications
                </p>
                {unreadNotifications.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-ink-400">You&apos;re all caught up.</p>
                ) : (
                  unreadNotifications.map((n) => (
                    <div
                      key={n.id}
                      className="px-3 py-2.5 rounded-lg hover:bg-ink-700/60"
                    >
                      <p className="text-sm font-medium text-ink-50">{n.title}</p>
                      <p className="text-xs text-ink-300 mt-0.5">{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          <Link href="/dashboard/settings" className="flex items-center gap-2">
            {user.image ? (
              <Image
                src={user.image}
                alt={user.name}
                width={36}
                height={36}
                className="h-9 w-9 rounded-full bg-ink-700"
                unoptimized
              />
            ) : (
              <span className="h-9 w-9 rounded-full bg-gold text-ink-950 text-sm font-bold flex items-center justify-center">
                {initials(user.name)}
              </span>
            )}
            <span className="hidden md:block text-sm text-ink-100">{user.name}</span>
          </Link>
        </header>

        <main className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">{children}</main>
      </div>

      {/* Bottom nav (mobile) */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-ink-700 bg-ink-950 grid grid-cols-5">
        {nav.slice(0, 5).map((item) => {
          const active =
            item.href === '/dashboard'
              ? pathname === '/dashboard'
              : pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-col items-center justify-center py-2 text-xs',
                active ? 'text-gold' : 'text-ink-300'
              )}
            >
              <item.icon size={18} />
              <span className="mt-0.5 text-[10px]">{item.label.split(' ')[0]}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
