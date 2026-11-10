import type { Country, FiatCurrency, Quote, RampProvider } from './types'
import { BitnobProvider } from './providers/bitnob'
import { TransakProvider } from './providers/transak'
import { DemoProvider } from './providers/demo'
import { prisma } from '../prisma'
import { decrypt } from '../crypto'

/**
 * The router picks the best Provider for a (country, currency) tuple.
 *
 * Preference order:
 *   1. CountryConfig.preferredProviderId (admin's explicit pick) if enabled + supports pair.
 *   2. A country-specialist provider that has real credentials.
 *   3. A global provider that has real credentials (Transak).
 *   4. A country-specialist in demo mode.
 *   5. The demo rail as the universal fallback — always works.
 *
 * Provider enable/disable and API keys are read from ProviderConfig when present;
 * env vars are the fallback. In-memory cache for 15 seconds so a quote call
 * doesn't hit the DB every time.
 */

const BASE_PROVIDERS: RampProvider[] = [
  new BitnobProvider(),
  new TransakProvider(),
  new DemoProvider(),
]

type OverrideMap = Record<
  string,
  { enabled: boolean; apiKey?: string; webhookSecret?: string; feeOverridePct?: number | null; priority: number }
>
type CountryMap = Record<string, { enabled: boolean; preferredProviderId: string | null }>

let cache: {
  loadedAt: number
  overrides: OverrideMap
  countries: CountryMap
} | null = null

const CACHE_MS = 15_000

async function loadOverrides(): Promise<{ overrides: OverrideMap; countries: CountryMap }> {
  if (cache && Date.now() - cache.loadedAt < CACHE_MS) {
    return { overrides: cache.overrides, countries: cache.countries }
  }
  const [providerRows, countryRows] = await Promise.all([
    prisma.providerConfig.findMany().catch(() => []),
    prisma.countryConfig.findMany().catch(() => []),
  ])
  const overrides: OverrideMap = {}
  for (const row of providerRows) {
    overrides[row.providerId] = {
      enabled: row.enabled,
      apiKey: row.apiKey ? decrypt(row.apiKey) : undefined,
      webhookSecret: row.webhookSecret ? decrypt(row.webhookSecret) : undefined,
      feeOverridePct: row.feeOverridePct,
      priority: row.priority,
    }
  }
  const countries: CountryMap = {}
  for (const row of countryRows) {
    countries[row.countryCode] = {
      enabled: row.enabled,
      preferredProviderId: row.preferredProviderId,
    }
  }
  cache = { loadedAt: Date.now(), overrides, countries }
  return { overrides, countries }
}

/** Invalidate the overrides cache after admin edits. */
export function invalidateRouterCache() {
  cache = null
}

function applyOverride(p: RampProvider, override?: OverrideMap[string]): RampProvider {
  if (!override) return p
  // Mutate the provider instance's env-backed fields through a simple proxy pattern:
  // the provider classes already read from process.env in their constructors, so
  // we expose a shim around isConfigured + a hidden apiKey.
  const proxy = Object.create(p) as RampProvider & { __apiKey?: string }
  // We treat "configured" as "has an apiKey from override OR provider reports configured".
  const hasOverrideKey = Boolean(override.apiKey && override.apiKey.length > 0)
  proxy.isConfigured = () => override.enabled !== false && (hasOverrideKey || p.isConfigured())
  return proxy
}

export async function listProviders(): Promise<RampProvider[]> {
  const { overrides } = await loadOverrides()
  return BASE_PROVIDERS.map((p) => applyOverride(p, overrides[p.id]))
}

export async function pickProvider(
  country: Country,
  currency: FiatCurrency
): Promise<RampProvider> {
  const { overrides, countries } = await loadOverrides()

  // If the admin disabled the country entirely, we still respond (with demo rail)
  // but the UI should be preventing this from being chosen.
  const countryCfg = countries[country]

  const candidates = BASE_PROVIDERS.filter((p) => {
    const override = overrides[p.id]
    if (override?.enabled === false) return false
    return p.supportedCountries.includes(country) && p.supportedCurrencies.includes(currency)
  }).map((p) => applyOverride(p, overrides[p.id]))

  // 1. Preferred-for-country wins if it matches and is configured (or demo).
  if (countryCfg?.preferredProviderId) {
    const preferred = candidates.find((p) => p.id === countryCfg.preferredProviderId)
    if (preferred) return preferred
  }

  // 2. Sort by (configured first, then priority DESC, then specialist first).
  const configured = candidates.filter((p) => p.isConfigured() && p.id !== 'demo')
  if (configured.length) {
    configured.sort((a, b) => {
      const pa = overrides[a.id]?.priority ?? 5
      const pb = overrides[b.id]?.priority ?? 5
      if (pb !== pa) return pb - pa
      return a.supportedCountries.length - b.supportedCountries.length
    })
    return configured[0]
  }

  // 3. Fall back to any specialist in demo mode (shorter supported-countries list wins).
  const specialists = candidates.filter(
    (p) => p.id !== 'demo' && p.supportedCountries.length < 20
  )
  if (specialists.length) {
    specialists.sort((a, b) => a.supportedCountries.length - b.supportedCountries.length)
    return specialists[0]
  }

  // 4. Universal demo rail.
  return applyOverride(BASE_PROVIDERS.find((p) => p.id === 'demo')!, overrides['demo'])
}

export async function getBestQuote(params: {
  country: Country
  currency: FiatCurrency
  amount: number
}): Promise<Quote> {
  const provider = await pickProvider(params.country, params.currency)
  return provider.quote({
    fromCurrency: params.currency,
    fromAmount: params.amount,
    country: params.country,
  })
}

/** Used by the admin dashboard to display all provider definitions + current state. */
export async function describeProviders() {
  const { overrides } = await loadOverrides()
  return BASE_PROVIDERS.map((p) => {
    const o = overrides[p.id]
    return {
      id: p.id,
      name: p.name,
      supportedCountries: p.supportedCountries,
      supportedCurrencies: p.supportedCurrencies,
      paymentMethods: p.paymentMethods,
      enabled: o?.enabled ?? true,
      hasKey: Boolean(o?.apiKey) || p.isConfigured(),
      hasWebhookSecret: Boolean(o?.webhookSecret),
      feeOverridePct: o?.feeOverridePct ?? null,
      priority: o?.priority ?? 5,
      isEnvConfigured: p.isConfigured(),
    }
  })
}
