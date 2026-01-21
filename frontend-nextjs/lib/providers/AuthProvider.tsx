'use client';

import { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from 'react';
import { authAPI, AuthUser } from '../api/auth';

const USER_CACHE_KEY = 'cached_user';

// Get cached user from localStorage asynchronously (non-blocking)
const getCachedUserAsync = (): Promise<AuthUser | null> => {
  return new Promise((resolve) => {
    if (typeof window === 'undefined') {
      resolve(null);
      return;
    }

    // Use microtask to avoid blocking render
    queueMicrotask(() => {
      try {
        const cached = localStorage.getItem(USER_CACHE_KEY);
        resolve(cached ? JSON.parse(cached) : null);
      } catch {
        resolve(null);
      }
    });
  });
};

// Save user to localStorage
const setCachedUser = (user: AuthUser | null) => {
  if (typeof window === 'undefined') return;
  try {
    if (user) {
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_CACHE_KEY);
    }
  } catch {}
};

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start with null to avoid hydration mismatch, then load from cache
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(false); // Don't block rendering
  const [initialized, setInitialized] = useState(false);
  const initRef = useRef(false);

  useEffect(() => {
    // Prevent double initialization in StrictMode
    if (initRef.current) return;
    initRef.current = true;

    // Load cached user asynchronously (non-blocking)
    const initAuth = async () => {
      const cached = await getCachedUserAsync();
      if (cached) {
        setUser(cached);
      }

      // Then verify with server
      if (authAPI.isAuthenticated()) {
        try {
          const freshUser = await authAPI.getCurrentUser();
          setUser(freshUser);
          setCachedUser(freshUser);
        } catch {
          setUser(null);
          setCachedUser(null);
        }
      } else {
        setUser(null);
        setCachedUser(null);
      }
      setInitialized(true);
    };

    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const user = await authAPI.login(email, password);
    setUser(user);
    setCachedUser(user);
  }, []);

  const register = useCallback(async (email: string, password: string, displayName?: string) => {
    const user = await authAPI.register(email, password, displayName);
    setUser(user);
    setCachedUser(user);
  }, []);

  const logout = useCallback(() => {
    authAPI.logout();
    setUser(null);
    setCachedUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
