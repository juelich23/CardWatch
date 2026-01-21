'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '@/lib/providers/AuthProvider';
import { useAISearch } from '@/lib/providers/AISearchProvider';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

const AuthModal = dynamic(() => import('./AuthModal').then(mod => ({ default: mod.AuthModal })), {
  ssr: false,
  loading: () => null,
});

const navLinks = [
  { href: '/', label: 'Browse' },
  { href: '/watchlist', label: 'Watchlist' },
];

export function Header() {
  const { user, logout } = useAuth();
  const { openAISearch } = useAISearch();
  const pathname = usePathname();
  const router = useRouter();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [mounted, setMounted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isMac, setIsMac] = useState(true); // Default to Mac, will update on mount

  useEffect(() => {
    setMounted(true);
    // Detect if user is on Mac
    const isMacOS = typeof navigator !== 'undefined' &&
      (navigator.platform.toUpperCase().indexOf('MAC') >= 0 ||
       navigator.userAgent.toUpperCase().indexOf('MAC') >= 0);
    setIsMac(isMacOS);
  }, []);

  const triggerCommandPalette = () => {
    const event = new KeyboardEvent('keydown', {
      key: 'k',
      metaKey: isMac,
      ctrlKey: !isMac,
      bubbles: true,
    });
    document.dispatchEvent(event);
  };

  const shortcutKey = isMac ? '⌘K' : 'Ctrl+K';

  const openLogin = () => {
    setAuthMode('login');
    setShowAuthModal(true);
    setMobileMenuOpen(false);
  };

  const openRegister = () => {
    setAuthMode('register');
    setShowAuthModal(true);
    setMobileMenuOpen(false);
  };

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <>
      <header className="sticky top-0 z-40 bg-panel/95 backdrop-blur-sm border-b border-border">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          {/* Logo */}
          <button
            onClick={() => router.push('/')}
            className="flex items-center gap-2 cursor-pointer"
          >
            <motion.h1
              className="text-xl sm:text-2xl font-bold text-text"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              CardWatch
            </motion.h1>
          </button>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive(link.href)
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-2 hover:text-text hover:bg-hover'
                }`}
              >
                {link.label}
              </Link>
            ))}

            {/* AI Search Button */}
            <button
              onClick={openAISearch}
              className="ml-2 px-3 py-1.5 text-sm font-medium text-accent bg-accent/10 border border-accent/30 rounded-md hover:bg-accent/20 transition-colors flex items-center gap-1.5"
            >
              <SparklesIcon />
              AI Search
            </button>

            {/* Command Palette Hint */}
            <button
              onClick={triggerCommandPalette}
              className="ml-2 px-2 py-1.5 text-xs text-muted bg-panel-2 border border-border rounded-md hover:border-accent/50 transition-colors flex items-center gap-1"
            >
              <kbd className="font-mono">{shortcutKey}</kbd>
            </button>

            <div className="h-6 w-px bg-border mx-3" />

            {/* Auth Section */}
            {!mounted ? (
              <div className="w-24 h-9" />
            ) : user ? (
              <div className="flex items-center gap-3">
                <span className="text-text text-sm truncate max-w-[120px]">
                  {user.displayName || user.email}
                </span>
                <Button variant="ghost" size="sm" onClick={logout}>
                  Sign Out
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={openLogin}>
                  Sign In
                </Button>
                <Button size="sm" onClick={openRegister}>
                  Register
                </Button>
              </div>
            )}
          </nav>

          {/* Mobile Menu */}
          <div className="flex items-center gap-2 md:hidden">
            {/* Command Palette Hint - Mobile */}
            <button
              onClick={triggerCommandPalette}
              className="p-2 text-muted hover:text-text transition-colors"
              aria-label="Open command palette"
            >
              <SearchIcon />
            </button>

            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <button
                  className="p-2 text-text-2 hover:text-text transition-colors"
                  aria-label="Open menu"
                >
                  <MenuIcon />
                </button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[280px] bg-panel border-border">
                <SheetHeader>
                  <SheetTitle className="text-text">Menu</SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col gap-1 mt-6">
                  {navLinks.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`px-4 py-3 rounded-lg text-base font-medium transition-colors ${
                        isActive(link.href)
                          ? 'bg-accent/10 text-accent'
                          : 'text-text-2 hover:text-text hover:bg-hover'
                      }`}
                    >
                      {link.label}
                    </Link>
                  ))}

                  <div className="h-px bg-border my-4" />

                  {/* Mobile Auth */}
                  {mounted && (
                    <>
                      {user ? (
                        <div className="px-4 py-2">
                          <p className="text-sm text-muted mb-1">Signed in as</p>
                          <p className="text-text font-medium truncate">
                            {user.displayName || user.email}
                          </p>
                          <Button
                            variant="outline"
                            className="w-full mt-3"
                            onClick={() => {
                              logout();
                              setMobileMenuOpen(false);
                            }}
                          >
                            Sign Out
                          </Button>
                        </div>
                      ) : (
                        <div className="px-4 flex flex-col gap-2">
                          <Button variant="outline" onClick={openLogin} className="w-full">
                            Sign In
                          </Button>
                          <Button onClick={openRegister} className="w-full">
                            Register
                          </Button>
                        </div>
                      )}
                    </>
                  )}

                  <div className="h-px bg-border my-4" />

                  {/* Quick Actions */}
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      openAISearch();
                    }}
                    className="px-4 py-3 rounded-lg text-base font-medium text-accent bg-accent/10 transition-colors flex items-center gap-2"
                  >
                    <SparklesIcon />
                    <span>AI Search</span>
                  </button>
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      setTimeout(triggerCommandPalette, 100);
                    }}
                    className="px-4 py-3 rounded-lg text-base font-medium text-text-2 hover:text-text hover:bg-hover transition-colors flex items-center justify-between"
                  >
                    <span>Quick Search</span>
                    <kbd className="text-xs bg-panel-2 px-2 py-1 rounded border border-border">{shortcutKey}</kbd>
                  </button>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode={authMode}
      />
    </>
  );
}

function MenuIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function SparklesIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
    </svg>
  );
}
