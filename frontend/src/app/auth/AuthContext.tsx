'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo, useCallback } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";

  useEffect(() => {
    // Check for existing token on mount
    const savedToken = localStorage.getItem('aegis_token');
    const savedExpiry = localStorage.getItem('aegis_token_expiry');
    
    if (savedToken && savedExpiry) {
      const now = new Date().getTime();
      const expiry = parseInt(savedExpiry);
      
      if (now < expiry) {
        setToken(savedToken);
        setIsAuthenticated(true);
      } else {
        // Token expired, clean up
        localStorage.removeItem('aegis_token');
        localStorage.removeItem('aegis_token_expiry');
      }
    }
    
    setLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/admin/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const data = await response.json();
        const token = data.access_token;
        const expiresIn = data.expires_in || 1800; // 30 minutes default
        const expiry = new Date().getTime() + (expiresIn * 1000);
        
        // Store token and expiry
        localStorage.setItem('aegis_token', token);
        localStorage.setItem('aegis_token_expiry', expiry.toString());
        
        setToken(token);
        setIsAuthenticated(true);
        setLoading(false);
        return true;
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Login failed');
        setLoading(false);
        return false;
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Network error. Please check your connection.');
      setLoading(false);
      return false;
    }
  }, [API_BASE]);

  const logout = useCallback(() => {
    localStorage.removeItem('aegis_token');
    localStorage.removeItem('aegis_token_expiry');
    setToken(null);
    setIsAuthenticated(false);
    setError(null);
  }, []);

  const contextValue = useMemo(() => ({
    isAuthenticated,
    token,
    login,
    logout,
    loading,
    error,
  }), [isAuthenticated, token, login, logout, loading, error]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};
