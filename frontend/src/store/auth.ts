import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthState, User } from '@/types';

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setToken: (token: string) => set({ token, isAuthenticated: true }),
      setUser: (user: User) => set({ user }),
      clearAuth: () => set({ token: null, user: null, isAuthenticated: false }),
    }),
    {
      name: 'energize-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
