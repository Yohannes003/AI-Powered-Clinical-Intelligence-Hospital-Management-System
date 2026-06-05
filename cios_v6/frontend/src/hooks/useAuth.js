import React, { createContext, useContext, useState, useCallback } from 'react';
import { authAPI } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cios_user')); } catch { return null; }
  });
  const [permissions, setPermissions] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cios_permissions') || '[]'); } catch { return []; }
  });
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    try {
      const res = await authAPI.login(email, password);
      const { access_token, user: userData, permissions: perms } = res.data;
      localStorage.setItem('cios_token', access_token);
      localStorage.setItem('cios_user', JSON.stringify(userData));
      localStorage.setItem('cios_permissions', JSON.stringify(perms || []));
      setUser(userData);
      setPermissions(perms || []);
      return { success: true, user: userData };
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed';
      return { success: false, error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('cios_token');
    localStorage.removeItem('cios_user');
    localStorage.removeItem('cios_permissions');
    setUser(null);
    setPermissions([]);
  }, []);

  // Check if current user has a specific permission
  const can = useCallback((permission) => {
    if (user?.role === 'admin') return true;
    return permissions.includes(permission);
  }, [permissions, user]);

  return (
    <AuthContext.Provider value={{ user, permissions, loading, login, logout, can, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
