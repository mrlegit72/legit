import { prisma } from '@/lib/prisma'
import { formatDateTime } from '@/lib/utils'

export const dynamic = 'force-dynamic'

export default async function AdminAuditPage() {
  const entries = await prisma.auditLog.findMany({
    orderBy: { createdAt: 'desc' },
    take: 200,
    include: { actor: { select: { name: true, email: true } } },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Audit log</h1>
        <p className="mt-1 text-ink-300">
          Append-only record of every admin action and material system event.
        </p>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-ink-400 bg-ink-900">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Time</th>
                <th className="text-left px-4 py-3 font-medium">Actor</th>
                <th className="text-left px-4 py-3 font-medium">Action</th>
                <th className="text-left px-4 py-3 font-medium">Target</th>
                <th className="text-left px-4 py-3 font-medium">Details</th>
                <th className="text-left px-4 py-3 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-ink-400">
                    No audit entries yet.
                  </td>
                </tr>
              ) : (
                entries.map((l) => (
                  <tr key={l.id} className="border-b border-ink-700/60 align-top">
                    <td className="px-4 py-3 text-xs text-ink-400 whitespace-nowrap">
                      {formatDateTime(l.createdAt)}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-ink-50">{l.actor?.name || 'System'}</p>
                      <p className="text-xs text-ink-400">{l.actor?.email || '—'}</p>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gold">{l.action}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-200">{l.target || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-300 max-w-md break-all">
                      {l.details || '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-400">{l.ip || '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
