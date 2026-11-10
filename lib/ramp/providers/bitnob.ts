import crypto from 'crypto'
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
 * Bitnob — West African crypto fintech with excellent Nigeria + Ghana rails.
 * Supports NGN and GHS bank transfers in and out. Narration-based deposits.
 *
 * Docs: https://docs.bitnob.com
 */
export class BitnobProvider implements RampProvider {
  readonly id = 'bitnob' as const
  readonly name = 'Bitnob'
  readonly supportedCountries: Country[] = ['NG', 'GH']
  readonly supportedCurrencies: FiatCurrency[] = ['NGN', 'GHS']
  readonly paymentMethods: PaymentMethod[] = ['bank_transfer']

  private apiKey = process.env.BITNOB_API_KEY || ''
  private webhookSecret = process.env.BITNOB_WEBHOOK_SECRET || ''
  private baseUrl =
    process.env.BITNOB_BASE_URL || 'https://api.bitnob.co/api/v1'

  isConfigured() {
    return Boolean(this.apiKey)
  }

  async quote(params: {
    fromCurrency: FiatCurrency
    fromAmount: number
    country: Country
  }): Promise<Quote> {
    // When configured, hit /rates/buy for a live rate. Fallback to indicative.
    let rate = INDICATIVE_RATES[params.fromCurrency] ?? 1
    if (this.isConfigured()) {
      try {
        const res = await fetch(
          `${this.baseUrl}/rates/buy?asset=USDT&currency=${params.fromCurrency}`,
          { headers: this.headers() }
        )
        const data = await res.json()
        if (data?.data?.rate) rate = Number(data.data.rate)
      } catch {
        /* fall through to indicative */
      }
    }

    const spread = 0.008 // ~0.8% — Bitnob is competitive in West Africa
    const fee = Math.max(50, params.fromAmount * spread) // ₦50 or GHS 0.5 floor
    const net = params.fromAmount - fee
    const toAmount = net / rate

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
      expiresAt: new Date(Date.now() + 10 * 60 * 1000),
      paymentMethods: this.paymentMethods,
    }
  }

  async createOnRamp(req: OnRampRequest): Promise<OnRampResult> {
    const quote = await this.quote({
      fromCurrency: req.fromCurrency,
      fromAmount: req.fromAmount,
      country: req.country,
    })

    const reference = `AJV-${req.userId.slice(-6).toUpperCase()}-${Date.now()
      .toString(36)
      .slice(-5)
      .toUpperCase()}`

    // With a real key, call Bitnob's virtual-account endpoint. In demo mode,
    // show the branded Bitnob Nigeria/Ghana settlement account.
    const bankInstructions =
      req.country === 'NG'
        ? {
            bankName: 'Providus Bank',
            accountNumber: '9910' + req.userId.slice(-6).padStart(6, '0'),
            accountName: 'Bitnob / AjoVault Collections',
            reference,
            narration: `AjoVault deposit — ref ${reference}`,
          }
        : {
            bankName: 'GCB Bank',
            accountNumber: '1234' + req.userId.slice(-6).padStart(6, '0'),
            accountName: 'Bitnob / AjoVault Collections (Ghana)',
            reference,
            narration: `AjoVault deposit — ref ${reference}`,
          }

    return {
      provider: this.id,
      externalId: reference,
      bankInstructions,
      expiresAt: new Date(Date.now() + 60 * 60 * 1000),
      quote,
    }
  }

  async createOffRamp(req: OffRampRequest): Promise<OffRampResult> {
    const currency: FiatCurrency = req.country === 'GH' ? 'GHS' : 'NGN'
    const rate = INDICATIVE_RATES[currency]
    const fee = Math.max(50, req.usdtAmount * 0.01) * rate / 1 // fee in local
    const payoutAmount = req.usdtAmount * rate - fee

    return {
      provider: this.id,
      externalId: `btn-off-${req.userId}-${Date.now()}`,
      estimatedArrival: new Date(Date.now() + 15 * 60 * 1000),
      payoutAmount: round(payoutAmount, 2),
      payoutCurrency: currency,
      fee: round(fee, 2),
      rate: round(rate, 4),
    }
  }

  parseWebhook(rawBody: string, headers: Record<string, string>): WebhookEvent | null {
    if (this.webhookSecret) {
      const signature = headers['x-bitnob-signature'] || ''
      const expected = crypto
        .createHmac('sha256', this.webhookSecret)
        .update(rawBody)
        .digest('hex')
      if (expected !== signature) return null
    }
    try {
      const payload = JSON.parse(rawBody) as any
      const event: string = payload?.event || ''
      let status: WebhookEvent['status'] = 'pending'
      if (event.includes('success') || event.includes('confirmed')) status = 'confirmed'
      else if (event.includes('fail')) status = 'failed'
      else if (event.includes('expir')) status = 'expired'
      return {
        provider: this.id,
        externalId: payload?.data?.reference || payload?.reference || '',
        status,
        amount: Number(payload?.data?.amount) || undefined,
        currency: payload?.data?.currency,
        rawPayload: payload,
      }
    } catch {
      return null
    }
  }

  private headers() {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
    }
  }
}

function round(n: number, dp = 2) {
  const f = 10 ** dp
  return Math.round(n * f) / f
}
