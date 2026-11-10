import { redirect } from 'next/navigation'
import { requireAdmin } from '@/lib/admin'
import { AdminShell } from '@/components/admin/AdminShell'

export const dynamic = 'force-dynamic'

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const admin = await requireAdmin()
  if (!admin) redirect('/dashboard')

  return (
    <AdminShell
      admin={{
        id: admin.id,
        name: admin.name,
        email: admin.email,
        image: admin.image,
      }}
    >
      {children}
    </AdminShell>
  )
}
