import type {
  Country,
  FiatCurrency,
  OnRampRequest,
  OnRampResult,
  OffRampRequest,
  OffRampResult,
  PaymentMethod,
  Quote,
  RampProvider,
  WebhookEvent,
} from '../types'
import { INDICATIVE_RATES } from '../countries'

/**
 * Demo provider — a working simulator that lets the UI be exercised end-to-end
 * without any partner credentials. It's the fallback when nothing real is
 * configured for a (country, currency) pair.
 */
export class DemoProvider implements RampProvider {
  readonly id = 'demo' as const
  readonly name = 'AjoVault Demo Rail'
  readonly supportedCountries: Country[] = [
    'NG', 'GH', 'KE', 'ZA', 'PH', 'IN', 'ID', 'MX', 'BR',
    'US', 'GB', 'EU', 'OTHER',
  ]
  readonly supportedCurrencies: FiatCurrency[] = [
    'NGN', 'GHS', 'KES', 'ZAR', 'PHP', 'INR', 'IDR', 'MXN', 'BRL',
    'USD', 'GBP', 'EUR',
  ]
  readonly paymentMethods: PaymentMethod[] = ['bank_transfer', 'card']

  isConfigured() {
    return true // always ready
  }

  async quote(params: {
    fromCurrency: FiatCurrency
    fromAmount: number
    country: Country
  }): Promise<Quote> {
    const rate = INDICATIVE_RATES[params.fromCurrency] ?? 1
    const spread = 0.015
    const fee = params.fromAmount * spread
    const toAmount = (params.fromAmount - fee) / rate

    return {
      provider: this.id,
      providerName: this.name,
      fromCurrency: params.fromCurrency,
      toCurrency: 'USDT',
      fromAmount: params.fromAmount,
      toAmount: round(toAmount, 2),
      rate: round(rate, 4),
      fee: round(fee, 2),
      total: round(params.fromAmount, 2),
      expiresAt: new Date(Date.now() + 15 * 60 * 1000),
      paymentMethods: this.paymentMethods,
    }
  }

  async createOnRamp(req: OnRampRequest): Promise<OnRampResult> {
    const quote = await this.quote({
      fromCurrency: req.fromCurrency,
      fromAmount: req.fromAmount,
      country: req.country,
    })
    const ref = `DEMO-${req.userId.slice(-6).toUpperCase()}-${Date.now()
      .toString(36)
      .slice(-5)
      .toUpperCase()}`
    return {
      provider: this.id,
      externalId: ref,
      bankInstructions: {
        bankName: 'Demo Settlement Bank',
        accountNumber: '0000-' + req.userId.slice(-6),
        accountName: 'AjoVault Demo Collections',
        reference: ref,
        narration: `Demo deposit — ref ${ref}`,
      },
      expiresAt: new Date(Date.now() + 60 * 60 * 1000),
      quote,
    }
  }

  async createOffRamp(req: OffRampRequest): Promise<OffRampResult> {
    const q = await this.quote({
      fromCurrency: 'USD',
      fromAmount: req.usdtAmount,
      country: req.country,
    })
    return {
      provider: this.id,
      externalId: `demo-off-${req.userId}-${Date.now()}`,
      estimatedArrival: new Date(Date.now() + 2 * 60 * 1000),
      payoutAmount: q.toAmount * (INDICATIVE_RATES[q.fromCurrency] ?? 1),
      payoutCurrency: 'USD',
      fee: q.fee,
      rate: q.rate,
    }
  }

  parseWebhook(): WebhookEvent | null {
    return null
  }
}

function round(n: number, dp = 2) {
  const f = 10 ** dp
  return Math.round(n * f) / f
}
