'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Minus } from 'lucide-react'

const faqs = [
  {
    q: 'Do I need to understand crypto to use AjoVault?',
    a: 'No. You sign up with email, top up in Naira or Cedi, and AjoVault quietly converts to USDT in the background. When you receive a payout, it lands in your local bank in minutes. Crypto is the plumbing — you never have to touch it.',
  },
  {
    q: 'What stops the coordinator from disappearing with our money?',
    a: 'There is no coordinator holding money. Contributions sit in an escrow wallet that only the rotation smart contract can release, on the schedule your group agreed to at setup.',
  },
  {
    q: 'What happens if a member stops contributing mid-cycle?',
    a: 'Their slot is frozen and the pot continues for the remaining members. Defaulters are flagged, and the group can vote to replace them with someone from the waitlist.',
  },
  {
    q: 'Is AjoVault legal in Nigeria and Ghana?',
    a: 'Yes. AjoVault is a digital cooperative savings tool. We hold no customer funds directly — payouts flow from escrow to licensed off-ramp partners for local settlement.',
  },
  {
    q: 'How do I get paid out in Naira / Cedi?',
    a: 'Add your bank details in Settings. When your rotation slot hits, we release the pot and you choose: keep it as USDT, or cash out instantly to your bank via our licensed partners.',
  },
]

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center"
        >
          <p className="text-sm font-medium text-gold uppercase tracking-widest">FAQ</p>
          <h2 className="mt-3 text-3xl sm:text-5xl font-bold tracking-tight">
            Questions, answered.
          </h2>
        </motion.div>

        <div className="mt-12 space-y-3">
          {faqs.map((f, i) => {
            const isOpen = open === i
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                className="card overflow-hidden"
              >
                <button
                  className="w-full flex items-center justify-between p-5 text-left"
                  onClick={() => setOpen(isOpen ? null : i)}
                >
                  <span className="font-medium text-ink-50">{f.q}</span>
                  {isOpen ? (
                    <Minus size={18} className="text-gold flex-shrink-0" />
                  ) : (
                    <Plus size={18} className="text-gold flex-shrink-0" />
                  )}
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden"
                    >
                      <p className="px-5 pb-5 text-ink-300 leading-relaxed">{f.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
