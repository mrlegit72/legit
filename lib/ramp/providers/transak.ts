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
 * Transak — global fiat on/off-ramp covering 170+ countries.
 * We use the hosted widget flow (simplest); the API key and env (staging
 * vs production) are configured via env vars.
 *
 * Docs: https://docs.transak.com
 */
export class TransakProvider implements RampProvider {
  readonly id = 'transak' as const
  readonly name = 'Transak'
  readonly supportedCountries: Country[] = [
    'US', 'GB', 'EU', 'IN', 'ID', 'MX', 'BR', 'ZA', 'PH', 'OTHER',
  ]
  readonly supportedCurrencies: FiatCurrency[] = [
    'USD', 'GBP', 'EUR', 'INR', 'IDR', 'MXN', 'BRL', 'ZAR', 'PHP',
  ]
  readonly paymentMethods: PaymentMethod[] = [
    'card', 'bank_transfer', 'apple_pay', 'google_pay',
  ]

  private apiKey = process.env.TRANSAK_API_KEY || ''
  private environment = (process.env.TRANSAK_ENV || 'STAGING').toUpperCase()

  private get widgetBase() {
    return this.environment === 'PRODUCTION'
      ? 'https://global.transak.com'
      : 'https://global-stg.transak.com'
  }

  isConfigured() {
    return Boolean(this.apiKey)
  }

  async quote(params: {
    fromCurrency: FiatCurrency
    fromAmount: number
    country: Country
  }): Promise<Quote> {
    // Transak's quote API requires a live key; without it we fall back to
    // the indicative mid-market rate and apply the partner's typical spread.
    const indicativeRate = INDICATIVE_RATES[params.fromCurrency] ?? 1
    const spread = 0.019 // ~1.9%, Transak's typical card spread
    const fee = Math.max(1, params.fromAmount * spread)
    const net = params.fromAmount - fee
    const toAmount = net / indicativeRate
    return {
      provider: this.id,
      providerName: this.name,
      fromCurrency: params.fromCurrency,
      toCurrency: 'USDT',
      fromAmount: params.fromAmount,
      toAmount: round(toAmount, 2),
      rate: round(indicativeRate, 4),
      fee: round(fee, 2),
      total: round(params.fromAmount, 2),
      expiresAt: new Date(Date.now() + 5 * 60 * 1000),
      paymentMethods: this.paymentMethods,
    }
  }

  async createOnRamp(req: OnRampRequest): Promise<OnRampResult> {
    const quote = await this.quote({
      fromCurrency: req.fromCurrency,
      fromAmount: req.fromAmount,
      country: req.country,
    })

    // Build a Transak hosted widget URL.
    const params = new URLSearchParams({
      apiKey: this.apiKey || 'demo',
      fiatCurrency: req.fromCurrency,
      fiatAmount: String(req.fromAmount),
      cryptoCurrencyCode: 'USDT',
      network: 'polygon',
      walletAddress: process.env.AJOVAULT_TREASURY_ADDRESS || '0xTreasury',
      email: req.userEmail,
      redirectURL: req.redirectUrl,
      partnerOrderId: `ajv-${req.userId}-${Date.now()}`,
    })
    const hostedUrl = `${this.widgetBase}/?${params.toString()}`

    return {
      provider: this.id,
      externalId: params.get('partnerOrderId')!,
      hostedUrl,
      expiresAt: new Date(Date.now() + 30 * 60 * 1000),
      quote,
    }
  }

  async createOffRamp(req: OffRampRequest): Promise<OffRampResult> {
    const rate = INDICATIVE_RATES[currencyFor(req.country)] ?? 1
    const fee = Math.max(1, req.usdtAmount * 0.012)
    const payoutAmount = (req.usdtAmount - fee) * rate
    return {
      provider: this.id,
      externalId: `tsk-off-${req.userId}-${Date.now()}`,
      estimatedArrival: new Date(Date.now() + 30 * 60 * 1000),
      payoutAmount: round(payoutAmount, 2),
      payoutCurrency: currencyFor(req.country),
      fee: round(fee, 2),
      rate: round(rate, 4),
    }
  }

  parseWebhook(rawBody: string): WebhookEvent | null {
    try {
      const payload = JSON.parse(rawBody) as any
      const status = mapStatus(payload?.status || payload?.eventID)
      return {
        provider: this.id,
        externalId: payload?.partnerOrderId || payload?.id || '',
        status,
        amount: Number(payload?.cryptoAmount) || undefined,
        currency: 'USDT',
        rawPayload: payload,
      }
    } catch {
      return null
    }
  }
}

function mapStatus(s: string): WebhookEvent['status'] {
  const u = (s || '').toUpperCase()
  if (u.includes('COMPLETED') || u.includes('SUCCESS')) return 'confirmed'
  if (u.includes('FAILED') || u.includes('CANCELLED')) return 'failed'
  if (u.includes('EXPIRED')) return 'expired'
  return 'pending'
}

function currencyFor(c: Country): FiatCurrency {
  const map: Partial<Record<Country, FiatCurrency>> = {
    US: 'USD', GB: 'GBP', EU: 'EUR', IN: 'INR', ID: 'IDR',
    MX: 'MXN', BR: 'BRL', ZA: 'ZAR', PH: 'PHP',
  }
  return map[c] || 'USD'
}

function round(n: number, dp = 2) {
  const f = 10 ** dp
  return Math.round(n * f) / f
}
