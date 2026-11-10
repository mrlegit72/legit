import type { Country, FiatCurrency, Quote, RampProvider } from './types'
import { BitnobProvider } from './providers/bitnob'
import { TransakProvider } from './providers/transak'
import { DemoProvider } from './providers/demo'

/**
 * The router picks the best Provider for a (country, currency) tuple.
 *
 * Preference order:
 *   1. A country-specialist provider that has real credentials
 *      (e.g. Bitnob for NG/GH when BITNOB_API_KEY is set).
 *   2. A global provider that has real credentials (Transak).
 *   3. A country-specialist in demo mode.
 *   4. The demo rail as the universal fallback — always works.
 *
 * This keeps a single API in front of a growing partner list, and lets us
 * roll out new countries by adding a new provider module.
 */

const providers: RampProvider[] = [
  new BitnobProvider(),
  new TransakProvider(),
  new DemoProvider(),
]

export function listProviders(): RampProvider[] {
  return providers
}

export function pickProvider(
  country: Country,
  currency: FiatCurrency
): RampProvider {
  const matches = providers.filter(
    (p) => p.supportedCountries.includes(country) && p.supportedCurrencies.includes(currency)
  )
  const configured = matches.filter((p) => p.isConfigured() && p.id !== 'demo')
  if (configured.length) {
    // Specialists first (shorter supportedCountries list = more focused).
    configured.sort((a, b) => a.supportedCountries.length - b.supportedCountries.length)
    return configured[0]
  }
  // Fall back to the demo rail.
  return providers.find((p) => p.id === 'demo')!
}

/**
 * Convenience helper: quote once, including the chosen provider in the result.
 */
export async function getBestQuote(params: {
  country: Country
  currency: FiatCurrency
  amount: number
}): Promise<Quote> {
  const provider = pickProvider(params.country, params.currency)
  return provider.quote({
    fromCurrency: params.currency,
    fromAmount: params.amount,
    country: params.country,
  })
}
