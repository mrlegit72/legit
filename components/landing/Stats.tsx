'use client'

import { motion } from 'framer-motion'

const stats = [
  { value: '₦2.3B+', label: 'Protected in escrow' },
  { value: '50,000+', label: 'Members saving' },
  { value: '12,000+', label: 'Groups completed' },
  { value: '0', label: 'Coordinator runaway cases' },
]

export function Stats() {
  return (
    <section className="relative py-16 sm:py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-ink-700 bg-gradient-to-br from-ink-800 to-ink-900 p-8 sm:p-12">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="text-center"
              >
                <p className="text-3xl sm:text-5xl font-bold gold-text">{s.value}</p>
                <p className="mt-2 text-sm text-ink-300">{s.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
