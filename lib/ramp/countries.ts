import type { Country, CountryInfo, FiatCurrency } from './types'

export const COUNTRIES: Record<Country, CountryInfo> = {
  NG: { code: 'NG', name: 'Nigeria', flag: '🇳🇬', currency: 'NGN', currencySymbol: '₦' },
  GH: { code: 'GH', name: 'Ghana', flag: '🇬🇭', currency: 'GHS', currencySymbol: '₵' },
  KE: { code: 'KE', name: 'Kenya', flag: '🇰🇪', currency: 'KES', currencySymbol: 'KSh' },
  ZA: { code: 'ZA', name: 'South Africa', flag: '🇿🇦', currency: 'ZAR', currencySymbol: 'R' },
  PH: { code: 'PH', name: 'Philippines', flag: '🇵🇭', currency: 'PHP', currencySymbol: '₱' },
  IN: { code: 'IN', name: 'India', flag: '🇮🇳', currency: 'INR', currencySymbol: '₹' },
  ID: { code: 'ID', name: 'Indonesia', flag: '🇮🇩', currency: 'IDR', currencySymbol: 'Rp' },
  MX: { code: 'MX', name: 'Mexico', flag: '🇲🇽', currency: 'MXN', currencySymbol: '$' },
  BR: { code: 'BR', name: 'Brazil', flag: '🇧🇷', currency: 'BRL', currencySymbol: 'R$' },
  US: { code: 'US', name: 'United States', flag: '🇺🇸', currency: 'USD', currencySymbol: '$' },
  GB: { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', currency: 'GBP', currencySymbol: '£' },
  EU: { code: 'EU', name: 'Europe', flag: '🇪🇺', currency: 'EUR', currencySymbol: '€' },
  OTHER: { code: 'OTHER', name: 'Other', flag: '🌍', currency: 'USD', currencySymbol: '$' },
}

/**
 * Indicative mid-market rates (USDT ≈ USD). Used only when no provider
 * returns a live quote. Keep these roughly current — they're visible to users.
 */
export const INDICATIVE_RATES: Record<FiatCurrency, number> = {
  NGN: 1630,
  GHS: 15.2,
  KES: 129.5,
  ZAR: 18.3,
  PHP: 58.1,
  INR: 83.8,
  IDR: 15800,
  MXN: 20.4,
  BRL: 5.75,
  USD: 1,
  GBP: 0.79,
  EUR: 0.92,
}

export function countryToString(country: string): Country {
  // The DB stores country as a free-form string ("Nigeria", "Ghana"). Map it back.
  const map: Record<string, Country> = {
    Nigeria: 'NG',
    Ghana: 'GH',
    Kenya: 'KE',
    'South Africa': 'ZA',
    Philippines: 'PH',
    India: 'IN',
    Indonesia: 'ID',
    Mexico: 'MX',
    Brazil: 'BR',
    'United States': 'US',
    USA: 'US',
    'United Kingdom': 'GB',
    UK: 'GB',
    Europe: 'EU',
  }
  if (country in map) return map[country]
  if (Object.keys(COUNTRIES).includes(country as Country)) return country as Country
  return 'OTHER'
}
