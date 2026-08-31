import React, { createContext, useContext, useEffect, useState } from 'react';

export type UserRole = 'client' | 'corp';

export interface User {
  id: string;
  email: string;
  role: UserRole;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (email: string, password: string, role: UserRole) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

async function extractErrorDetail(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) {
    return `${res.status} ${res.statusText}`;
  }
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === 'string') return parsed.detail;
    if (Array.isArray(parsed?.detail)) {
      return parsed.detail
        .map((d: { msg?: string }) => d?.msg || '')
        .filter(Boolean)
        .join('; ');
    }
    return text;
  } catch {
    return text;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch('/auth/me', { credentials: 'include' })
      .then((res) => {
        if (!res.ok) throw new Error('Not authenticated');
        return res.json();
      })
      .then((profile) => {
        if (active) setUser(profile);
      })
      .catch(() => {
        // No active session
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const login = async (email: string, password: string): Promise<User> => {
    const res = await fetch('/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      throw new Error(await extractErrorDetail(res) || 'Login failed');
    }
    const data = await res.json();
    setUser(data.user);
    return data.user;
  };

  const signup = async (email: string, password: string, role: UserRole): Promise<User> => {
    const res = await fetch('/auth/signup', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role }),
    });
    if (!res.ok) {
      throw new Error(await extractErrorDetail(res) || 'Signup failed');
    }
    const data = await res.json();
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
    } catch {
      // Ignore network errors during logout
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
