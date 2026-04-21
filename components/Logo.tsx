import { Vault } from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

export function Logo({
  className,
  size = 'md',
  href = '/',
}: {
  className?: string
  size?: 'sm' | 'md' | 'lg'
  href?: string | null
}) {
  const sizes = {
    sm: { icon: 18, text: 'text-lg' },
    md: { icon: 22, text: 'text-xl' },
    lg: { icon: 28, text: 'text-2xl' },
  }[size]

  const content = (
    <span className={cn('flex items-center gap-2 font-bold tracking-tight', className)}>
      <span className="relative inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-gold to-gold-700 shadow-gold">
        <Vault size={sizes.icon} className="text-ink-950" strokeWidth={2.5} />
      </span>
      <span className={cn(sizes.text, 'gold-text')}>AjoVault</span>
    </span>
  )

  if (href === null) return content
  return <Link href={href}>{content}</Link>
}
