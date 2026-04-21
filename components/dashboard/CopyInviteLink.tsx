'use client'

import { useState } from 'react'
import { Check, Copy, Link as LinkIcon } from 'lucide-react'
import toast from 'react-hot-toast'

export function CopyInviteLink({ inviteCode }: { inviteCode: string }) {
  const [copied, setCopied] = useState(false)
  const url =
    typeof window !== 'undefined'
      ? `${window.location.origin}/invite/${inviteCode}`
      : `/invite/${inviteCode}`

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      toast.success('Invite link copied')
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy')
    }
  }

  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 hover:border-gold/40 hover:text-gold"
    >
      <LinkIcon size={14} />
      <span className="max-w-[200px] truncate">{url}</span>
      {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
    </button>
  )
}
