import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User } from '../types';
import { authApi } from '../api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ mfa_required?: boolean; temp_token?: string }>;
  loginMfa: (totp_code: string, temp_token: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) { setLoading(false); return; }
    try {
      const res = await authApi.me();
      setUser(res.data);
    } catch {
      localStorage.removeItem('access_token');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    const data = res.data as {
      mfa_required?: boolean;
      temp_token?: string;
      access_token?: string;
      refresh_token?: string;
    };
    if (data.mfa_required) {
      return { mfa_required: true, temp_token: data.temp_token || '' };
    }
    localStorage.setItem('access_token', data.access_token!);
    const me = await authApi.me();
    setUser(me.data);
    return {};
  };

  const loginMfa = async (totp_code: string, temp_token: string) => {
    const res = await authApi.loginMfa({ totp_code, temp_token });
    const data = res.data as { access_token: string };
    localStorage.setItem('access_token', data.access_token);
    const me = await authApi.me();
    setUser(me.data);
  };

  const register = async (email: string, password: string, full_name: string) => {
    const res = await authApi.register({ email, password, full_name });
    const data = res.data as { access_token: string };
    localStorage.setItem('access_token', data.access_token);
    const me = await authApi.me();
    setUser(me.data);
  };

  const logout = () => {
    authApi.logout().catch(() => {});
    localStorage.removeItem('access_token');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, loginMfa, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
