import Link from 'next/link'
import { Twitter, Instagram, Linkedin, Github } from 'lucide-react'
import { Logo } from '@/components/Logo'

export function Footer() {
  return (
    <footer className="border-t border-ink-700 bg-ink-950">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="md:col-span-1">
            <Logo />
            <p className="mt-4 text-sm text-ink-300 max-w-xs">
              Your group savings. Protected by crypto. Trusted by all.
            </p>
            <div className="mt-6 flex gap-3">
              {[Twitter, Instagram, Linkedin, Github].map((Icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="h-9 w-9 rounded-lg border border-ink-700 flex items-center justify-center text-ink-300 hover:text-gold hover:border-gold transition"
                >
                  <Icon size={16} />
                </a>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-ink-50 mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-ink-300">
              <li><a href="#features" className="hover:text-gold">Features</a></li>
              <li><a href="#pricing" className="hover:text-gold">Pricing</a></li>
              <li><a href="#how" className="hover:text-gold">How it works</a></li>
              <li><Link href="/auth/register" className="hover:text-gold">Get started</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-ink-50 mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-ink-300">
              <li><a href="#" className="hover:text-gold">About</a></li>
              <li><a href="#" className="hover:text-gold">Blog</a></li>
              <li><a href="#" className="hover:text-gold">Careers</a></li>
              <li><a href="#" className="hover:text-gold">Contact</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-ink-50 mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-ink-300">
              <li><a href="#" className="hover:text-gold">Terms</a></li>
              <li><a href="#" className="hover:text-gold">Privacy</a></li>
              <li><a href="#" className="hover:text-gold">Security</a></li>
              <li><a href="#" className="hover:text-gold">Compliance</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-8 border-t border-ink-700 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-ink-400">
            © {new Date().getFullYear()} AjoVault Technologies. All rights reserved.
          </p>
          <p className="text-xs text-ink-400">
            Made for Africa, powered by crypto.
          </p>
        </div>
      </div>
    </footer>
  )
}
