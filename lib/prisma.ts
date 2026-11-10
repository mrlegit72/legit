import { PrismaClient } from '@prisma/client'
import fs from 'fs'
import path from 'path'

// Ephemeral-DB bootstrap for serverless (Vercel).
// SQLite on Vercel lives in /tmp (writable but ephemeral per Lambda instance).
// On cold start, copy the bundled seed DB into /tmp and point Prisma at it.
// State persists for the lifetime of a Lambda instance (~minutes to ~hours),
// then resets to seed data on the next cold start. Fine for demos.
function resolveDatabaseUrl(): string {
  const existing = process.env.DATABASE_URL
  if (existing && !existing.includes('./dev.db') && !existing.includes('/tmp/')) {
    // Caller set an explicit URL (e.g. local dev with file:./dev.db, or a real Postgres).
    return existing
  }

  // On Vercel / read-only hosts, boot an ephemeral copy in /tmp.
  const isServerless = Boolean(process.env.VERCEL)
  if (!isServerless) {
    return existing || 'file:./dev.db'
  }

  const tmpDb = '/tmp/ajovault.db'
  try {
    if (!fs.existsSync(tmpDb)) {
      // Candidate locations where the seed DB may land after Next.js output-file-tracing.
      const candidates = [
        path.join(process.cwd(), 'data', 'seed.db'),
        path.join(process.cwd(), '.next', 'server', 'data', 'seed.db'),
        path.resolve(__dirname, '..', 'data', 'seed.db'),
        path.resolve(__dirname, '..', '..', 'data', 'seed.db'),
      ]
      const source = candidates.find((p) => {
        try {
          return fs.existsSync(p)
        } catch {
          return false
        }
      })
      if (source) {
        fs.copyFileSync(source, tmpDb)
      } else {
        // Nothing found — let Prisma create an empty DB (first request will crash gracefully).
        console.warn('[prisma] no seed.db found; starting with empty /tmp DB')
      }
    }
  } catch (e) {
    console.error('[prisma] bootstrap failed:', e)
  }

  return `file:${tmpDb}`
}

const databaseUrl = resolveDatabaseUrl()

const globalForPrisma = global as unknown as { prisma: PrismaClient }

export const prisma =
  globalForPrisma.prisma ||
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
    datasources: { db: { url: databaseUrl } },
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
