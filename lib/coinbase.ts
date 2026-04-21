import axios from 'axios'
import crypto from 'crypto'

const COINBASE_API = 'https://api.commerce.coinbase.com'

const coinbaseHeaders = () => ({
  'X-CC-Api-Key': process.env.COINBASE_COMMERCE_API_KEY || '',
  'X-CC-Version': '2018-03-22',
  'Content-Type': 'application/json',
})

export async function createCharge(params: {
  userId: string
  amount: string
  currency: string
  description: string
  metadata?: Record<string, string>
}) {
  const response = await axios.post(
    `${COINBASE_API}/charges`,
    {
      name: 'AjoVault Deposit',
      description: params.description,
      pricing_type: 'fixed_price',
      local_price: {
        amount: params.amount,
        currency: params.currency,
      },
      metadata: {
        userId: params.userId,
        ...params.metadata,
      },
      redirect_url: `${process.env.NEXTAUTH_URL}/dashboard/wallet?status=success`,
      cancel_url: `${process.env.NEXTAUTH_URL}/dashboard/wallet?status=cancelled`,
    },
    { headers: coinbaseHeaders() }
  )
  return response.data.data
}

export async function getCharge(chargeId: string) {
  const response = await axios.get(`${COINBASE_API}/charges/${chargeId}`, {
    headers: coinbaseHeaders(),
  })
  return response.data.data
}

export async function listCharges() {
  const response = await axios.get(`${COINBASE_API}/charges`, {
    headers: coinbaseHeaders(),
  })
  return response.data.data
}

export function verifyWebhookSignature(
  rawBody: string,
  signature: string,
  secret: string
): boolean {
  const hmac = crypto.createHmac('sha256', secret)
  hmac.update(rawBody)
  const computedSignature = hmac.digest('hex')
  return computedSignature === signature
}

export function hasCoinbaseConfigured() {
  return Boolean(process.env.COINBASE_COMMERCE_API_KEY)
}
