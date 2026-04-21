'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { ArrowRight, Shield, Sparkles } from 'lucide-react'

export function Hero() {
  return (
    <section className="relative pt-28 pb-20 sm:pt-36 sm:pb-32 noise-bg">
      <div className="absolute inset-0 grid-bg opacity-40 pointer-events-none" />
      <div className="absolute left-1/2 top-20 -z-0 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-gold/10 blur-3xl" />

      {/* Floating particles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {[...Array(12)].map((_, i) => (
          <motion.span
            key={i}
            className="absolute block h-1.5 w-1.5 rounded-full bg-gold/60"
            style={{
              left: `${(i * 83) % 100}%`,
              top: `${(i * 47) % 80 + 10}%`,
            }}
            animate={{
              y: [0, -20, 0],
              opacity: [0.2, 0.8, 0.2],
            }}
            transition={{
              duration: 3 + (i % 4),
              repeat: Infinity,
              delay: i * 0.3,
            }}
          />
        ))}
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-4 py-1.5 text-xs sm:text-sm text-gold"
          >
            <Sparkles size={14} />
            <span>Now live in Nigeria & Ghana — 50,000+ members trust AjoVault</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="mt-8 text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-tight"
          >
            Your group savings.
            <br />
            <span className="gold-text">Protected by crypto.</span>
            <br />
            Trusted by all.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-6 text-lg sm:text-xl text-ink-200 max-w-2xl mx-auto"
          >
            AjoVault turns traditional Ajo/Susu groups into a transparent, escrow-backed savings
            experience — powered by USDT so no coordinator can ever disappear with your money.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3"
          >
            <Link href="/auth/register" className="btn-gold w-full sm:w-auto text-base px-7 py-3.5">
              Start a Group <ArrowRight size={18} />
            </Link>
            <Link href="/auth/login" className="btn-ghost w-full sm:w-auto text-base px-7 py-3.5">
              Join a Group
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-10 inline-flex items-center gap-2 text-sm text-ink-300"
          >
            <Shield size={16} className="text-emerald-400" />
            Non-custodial escrow. Smart rotation. Zero coordinator risk.
          </motion.div>
        </div>

        {/* Mock dashboard preview */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="relative mt-16 mx-auto max-w-5xl"
        >
          <div className="absolute -inset-4 bg-gold/20 blur-3xl rounded-3xl" />
          <div className="relative rounded-2xl border border-ink-700 bg-gradient-to-b from-ink-800 to-ink-900 p-4 sm:p-6 shadow-gold-lg">
            <div className="flex items-center gap-1.5 mb-4">
              <span className="h-3 w-3 rounded-full bg-red-500/60" />
              <span className="h-3 w-3 rounded-full bg-gold/60" />
              <span className="h-3 w-3 rounded-full bg-emerald-500/60" />
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl bg-ink-900 border border-ink-700 p-4">
                <p className="text-xs text-ink-300">Total Saved</p>
                <p className="mt-2 text-2xl font-bold gold-text">4,280 USDT</p>
                <p className="mt-1 text-xs text-emerald-400">+ 340 this month</p>
              </div>
              <div className="rounded-xl bg-ink-900 border border-ink-700 p-4">
                <p className="text-xs text-ink-300">Active Groups</p>
                <p className="mt-2 text-2xl font-bold text-ink-50">3</p>
                <p className="mt-1 text-xs text-ink-300">2 payouts incoming</p>
              </div>
              <div className="rounded-xl bg-ink-900 border border-ink-700 p-4">
                <p className="text-xs text-ink-300">Next Payout</p>
                <p className="mt-2 text-2xl font-bold text-ink-50">in 6 days</p>
                <p className="mt-1 text-xs text-gold">1,200 USDT</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
