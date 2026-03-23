'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthStore } from '@/store/auth';
import { User } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

function normalizeRoles(raw: unknown): string[] {
  if (raw == null) return [];
  if (typeof raw === 'string') {
    return raw
      .split(',')
      .map((r) => r.trim().toLowerCase())
      .filter(Boolean);
  }
  if (Array.isArray(raw)) {
    return raw
      .filter((r): r is string => typeof r === 'string')
      .map((r) => r.trim().toLowerCase())
      .filter(Boolean);
  }
  return [];
}

function resolveRole(profile: any): 'admin' | 'coach' | 'client' {
  const flatRoles = normalizeRoles(profile?.roles);
  const singularRole = normalizeRoles(profile?.role);
  const dottedRealmRoles = normalizeRoles(profile?.['realm_access.roles']);
  const realmRoles = normalizeRoles(profile?.realm_access?.roles);
  const resourceAccess = profile?.resource_access || {};
  const clientRoles: string[] = Object.values(resourceAccess)
    .flatMap((entry: any) => normalizeRoles(entry?.roles));

  const dynamicRoleClaims: string[] = Object.entries(profile || {})
    .filter(([key]) => String(key).toLowerCase().endsWith('roles'))
    .flatMap(([, value]) => normalizeRoles(value));

  const roles = new Set([
    ...flatRoles,
    ...singularRole,
    ...dottedRealmRoles,
    ...realmRoles,
    ...clientRoles,
    ...dynamicRoleClaims,
  ]);
  if (roles.has('admin') || roles.has('realm-admin') || roles.has('super-admin') || roles.has('super_admin')) {
    return 'admin';
  }
  if (roles.has('coach') || roles.has('energize-coach')) return 'coach';
  return 'client';
}

async function fetchCurrentUser(token: string, fallbackProfile: any): Promise<User> {
  const fallbackUser: User = {
    id: fallbackProfile?.sub || '',
    email: fallbackProfile?.email || '',
    name: fallbackProfile?.given_name
      || fallbackProfile?.name
      || fallbackProfile?.preferred_username
      || '',
    preferredUsername: fallbackProfile?.preferred_username || '',
    role: resolveRole(fallbackProfile),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      return fallbackUser;
    }

    const data = await response.json();
    return {
      id: data.id || fallbackUser.id,
      email: data.email || fallbackUser.email,
      name: fallbackUser.name || data.email || '',
      preferredUsername: fallbackUser.preferredUsername,
      role: data.role || fallbackUser.role,
    };
  } catch {
    return fallbackUser;
  }
}

export function useAuth() {
  const { token, user, isAuthenticated, setToken, setUser, clearAuth } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const initStartedRef = useRef(false);

  const initKeycloak = useCallback(async () => {
    if (typeof window === 'undefined') return;
    if (initStartedRef.current) return;
    initStartedRef.current = true;
    setIsLoading(true);
    try {
      const { getKeycloak } = await import('@/lib/keycloak');
      const kc = getKeycloak();

      if (kc.authenticated && kc.token) {
        setToken(kc.token);
        const profile = kc.tokenParsed;
        if (profile) {
          const userInfo = await fetchCurrentUser(kc.token, profile as any);
          setUser(userInfo);
        }
        return;
      }

      const authenticated = await kc.init({
        onLoad: 'login-required',
        checkLoginIframe: false,
        scope: 'openid profile email roles',
      });

      if (authenticated) {
        const kcToken = kc.token!;
        setToken(kcToken);

        const profile = kc.tokenParsed;
        if (profile) {
          const userInfo = await fetchCurrentUser(kcToken, profile as any);
          setUser(userInfo);
        }

        // Refresh token before expiry
        setInterval(async () => {
          try {
            const refreshed = await kc.updateToken(60);
            if (refreshed && kc.token) {
              setToken(kc.token);
              const refreshedProfile = kc.tokenParsed;
              if (refreshedProfile) {
                const userInfo = await fetchCurrentUser(kc.token, refreshedProfile as any);
                setUser(userInfo);
              }
            }
          } catch {
            clearAuth();
          }
        }, 30000);
      }
    } catch (error) {
      console.error('Keycloak init error:', error);
      clearAuth();
    } finally {
      setIsLoading(false);
      initStartedRef.current = false;
    }
  }, [setToken, setUser, clearAuth]);

  const logout = useCallback(async () => {
    if (typeof window === 'undefined') return;
    try {
      const { getKeycloak } = await import('@/lib/keycloak');
      const kc = getKeycloak();
      clearAuth();
      await kc.logout({ redirectUri: window.location.origin + '/login' });
    } catch {
      clearAuth();
      window.location.href = '/login';
    }
  }, [clearAuth]);

  return { token, user, isAuthenticated, isLoading, initKeycloak, logout };
}
