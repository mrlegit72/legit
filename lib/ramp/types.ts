/**
 * Common types for the AjoVault global fiat on-ramp / off-ramp layer.
 *
 * The product is borderless because USDT is borderless. Only the
 * fiat ↔ USDT conversion step is country-specific. This module gives
 * every country-specific partner the same shape so a new country =
 * a new Provider module, nothing else.
 *
 * Flow:
 *   User local currency (NGN/KES/INR/...)
 *      ↓ on-ramp Provider (Transak / Bitnob / Kotani / ...)
 *   USDT in AjoVault escrow
 *      ↓ off-ramp Provider (same partner set)
 *   User's bank in their local currency
 */

export type Country =
  | 'NG' // Nigeria
  | 'GH' // Ghana
  | 'KE' // Kenya
  | 'ZA' // South Africa
  | 'PH' // Philippines
  | 'IN' // India
  | 'ID' // Indonesia
  | 'MX' // Mexico
  | 'BR' // Brazil
  | 'US' // United States
  | 'GB' // United Kingdom
  | 'EU' // EU catch-all
  | 'OTHER'

export type FiatCurrency =
  | 'NGN'
  | 'GHS'
  | 'KES'
  | 'ZAR'
  | 'PHP'
  | 'INR'
  | 'IDR'
  | 'MXN'
  | 'BRL'
  | 'USD'
  | 'GBP'
  | 'EUR'

export type PaymentMethod =
  | 'bank_transfer'
  | 'mobile_money'
  | 'card'
  | 'apple_pay'
  | 'google_pay'
  | 'wire'

export type ProviderId =
  | 'transak'
  | 'bitnob'
  | 'kotani'
  | 'bitso'
  | 'coinbase'
  | 'demo'

/** Metadata shown in the UI for each country. */
export interface CountryInfo {
  code: Country
  name: string
  flag: string
  currency: FiatCurrency
  currencySymbol: string
}

export interface Quote {
  provider: ProviderId
  providerName: string
  fromCurrency: FiatCurrency
  toCurrency: 'USDT'
  fromAmount: number
  toAmount: number
  rate: number // 1 USDT = `rate` fromCurrency
  fee: number // in fromCurrency
  total: number // fromAmount + fee (what the user actually pays)
  expiresAt: Date
  paymentMethods: PaymentMethod[]
}

export interface OnRampRequest {
  userId: string
  userEmail: string
  userName: string
  country: Country
  fromCurrency: FiatCurrency
  fromAmount: number
  paymentMethod?: PaymentMethod
  redirectUrl: string
}

export interface OnRampResult {
  provider: ProviderId
  externalId: string // the partner's reference for this transaction
  hostedUrl?: string // for redirect-based providers (Transak, MoonPay)
  bankInstructions?: BankInstructions // for bank-transfer providers (Bitnob, Kotani)
  expiresAt: Date
  quote: Quote
}

export interface BankInstructions {
  bankName: string
  accountNumber: string
  accountName: string
  reference: string // user must include this in their bank transfer narration
  narration?: string
}

export interface OffRampRequest {
  userId: string
  userName: string
  country: Country
  usdtAmount: number
  bankDetails: BankDetails
}

export interface BankDetails {
  bankName: string
  accountNumber: string
  accountName: string
  bankCode?: string // required in some countries (e.g. Nigeria uses NIP codes)
  swift?: string // for international wires
}

export interface OffRampResult {
  provider: ProviderId
  externalId: string
  estimatedArrival: Date
  payoutAmount: number // what the user will actually receive in local currency
  payoutCurrency: FiatCurrency
  fee: number
  rate: number
}

export interface WebhookEvent {
  provider: ProviderId
  externalId: string
  status: 'pending' | 'confirmed' | 'failed' | 'expired'
  amount?: number
  currency?: string
  rawPayload: unknown
}

/**
 * The contract every country-specific partner implements.
 * Adding a new country = implementing this interface for its partner.
 */
export interface RampProvider {
  readonly id: ProviderId
  readonly name: string
  readonly supportedCountries: Country[]
  readonly supportedCurrencies: FiatCurrency[]
  readonly paymentMethods: PaymentMethod[]

  /** True when this provider is wired up with real credentials (not demo). */
  isConfigured(): boolean

  /** Returns a live quote for converting `fromAmount` fromCurrency → USDT. */
  quote(params: {
    fromCurrency: FiatCurrency
    fromAmount: number
    country: Country
  }): Promise<Quote>

  /** Starts an on-ramp (deposit). */
  createOnRamp(request: OnRampRequest): Promise<OnRampResult>

  /** Starts an off-ramp (withdrawal to local bank). */
  createOffRamp(request: OffRampRequest): Promise<OffRampResult>

  /** Verify a webhook signature + parse into a normalized event. */
  parseWebhook(rawBody: string, headers: Record<string, string>): WebhookEvent | null
}
