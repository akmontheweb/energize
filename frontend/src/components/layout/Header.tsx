'use client';

import { useAuth } from '@/hooks/useAuth';
import { useState } from 'react';
import { ChangePasswordModal } from '@/components/auth/ChangePasswordModal';

export function Header() {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
  }

  const firstName = user
    ? (() => {
        const raw = user.name && !user.name.includes('@')
          ? user.name
          : (user.preferredUsername && !user.preferredUsername.includes('@')
              ? user.preferredUsername
              : user.email.split('@')[0]);
        return raw.split(' ')[0];
      })()
    : '';

  const initials = firstName
    ? firstName.slice(0, 2).toUpperCase()
    : (user?.email.slice(0, 2).toUpperCase() ?? '??');

  return (
    <>
    <header className="h-14 bg-slate-800 border-b border-slate-700 flex items-center px-4 gap-3 z-10">
      <div className="flex items-center gap-2 mr-4">
        <img src="/logo.svg" alt="Energize" className="h-9 w-auto" />
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-3">
        {user && (
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center">
              <span className="text-white text-xs font-semibold">{initials}</span>
            </div>
            <div className="hidden sm:flex flex-col">
              <span className="text-sm font-medium text-white leading-tight">
                Hi {firstName}
              </span>
            </div>
          </div>
        )}
        {user && (user.role === 'client' || user.role === 'coach') && (
          <button
            onClick={() => setShowChangePassword(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 hover:text-white hover:bg-slate-700 rounded-md transition-colors"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <span className="hidden sm:inline">Change Password</span>
          </button>
        )}
        <button
          onClick={handleLogout}
          disabled={loggingOut}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 hover:text-white hover:bg-slate-700 rounded-md transition-colors disabled:opacity-50"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span className="hidden sm:inline">{loggingOut ? 'Logging out…' : 'Logout'}</span>
        </button>
      </div>
    </header>
    {showChangePassword && (
      <ChangePasswordModal onClose={() => setShowChangePassword(false)} />
    )}
  </>
  );
}
