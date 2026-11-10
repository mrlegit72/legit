import crypto from 'crypto'

/**
 * AES-256-GCM helpers for storing partner API keys at rest in the DB.
 * The data encryption key is derived from NEXTAUTH_SECRET so all services
 * that already have the secret can decrypt (same host, no extra config).
 * In a future prod hardening pass, move to a dedicated KMS or at least
 * rotate the DEK independently.
 */

function deriveKey(): Buffer {
  const material =
    process.env.ADMIN_ENCRYPTION_KEY ||
    process.env.NEXTAUTH_SECRET ||
    'ajovault-dev-encryption-fallback'
  return crypto.createHash('sha256').update(material).digest()
}

const ALGO = 'aes-256-gcm'

export function encrypt(plaintext: string): string {
  if (!plaintext) return ''
  const iv = crypto.randomBytes(12)
  const key = deriveKey()
  const cipher = crypto.createCipheriv(ALGO, key, iv)
  const enc = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  // Base64(iv:tag:ciphertext)
  return Buffer.concat([iv, tag, enc]).toString('base64')
}

export function decrypt(ciphertext: string): string {
  if (!ciphertext) return ''
  try {
    const buf = Buffer.from(ciphertext, 'base64')
    const iv = buf.subarray(0, 12)
    const tag = buf.subarray(12, 28)
    const enc = buf.subarray(28)
    const key = deriveKey()
    const decipher = crypto.createDecipheriv(ALGO, key, iv)
    decipher.setAuthTag(tag)
    const dec = Buffer.concat([decipher.update(enc), decipher.final()])
    return dec.toString('utf8')
  } catch {
    return ''
  }
}

/** Return a redacted preview of a secret so the admin UI can confirm what's stored. */
export function maskSecret(plaintext: string): string {
  if (!plaintext) return ''
  if (plaintext.length <= 8) return '••••'
  return `${plaintext.slice(0, 4)}••••${plaintext.slice(-4)}`
}
