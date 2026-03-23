'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Session } from '@/types';
import { sessionsApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/hooks/useAuth';

const statusColors: Record<Session['status'], string> = {
  active: 'bg-green-100 text-green-700',
  completed: 'bg-gray-100 text-gray-600',
  escalated: 'bg-red-100 text-red-700',
  archived: 'bg-yellow-100 text-yellow-700',
};

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const role = user?.role ?? 'client';
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    sessionsApi.list()
      .then((data) => { if (!cancelled) setSessions(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    function onSessionUpdated(e: Event) {
      const updated = (e as CustomEvent).detail;
      if (!updated?.id) return;
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    }
    function onSessionCreated(e: Event) {
      const created = (e as CustomEvent).detail;
      if (!created?.id) return;
      setSessions((prev) => [created, ...prev.filter((s) => s.id !== created.id)]);
    }
    function onSessionDeleted(e: Event) {
      const { id } = (e as CustomEvent<{ id: string }>).detail;
      if (!id) return;
      setSessions((prev) => prev.filter((s) => s.id !== id));
    }
    window.addEventListener('sessionUpdated', onSessionUpdated);
    window.addEventListener('sessionCreated', onSessionCreated);
    window.addEventListener('sessionDeleted', onSessionDeleted);
    return () => {
      window.removeEventListener('sessionUpdated', onSessionUpdated);
      window.removeEventListener('sessionCreated', onSessionCreated);
      window.removeEventListener('sessionDeleted', onSessionDeleted);
    };
  }, []);

  async function handleNewSession() {
    const titleInput = window.prompt('Enter a session name', 'My Coaching Session');
    if (titleInput === null) return;

    const title = titleInput.trim();
    setCreating(true);
    try {
      const session = await sessionsApi.create({ title: title || 'New Coaching Session' });
      setSessions((prev) => [session, ...prev]);
      router.push(`/chat/${session.id}`);
    } catch (err) {
      console.error('Failed to create session', err);
    } finally {
      setCreating(false);
    }
  }

  return (
    <aside className="w-64 flex-shrink-0 bg-gray-900 text-white flex flex-col h-full">
      {/* Sidebar header */}
      <div className="px-4 py-4 border-b border-gray-700">
        {role === 'client' && (
          <Button
            variant="primary"
            size="sm"
            loading={creating}
            onClick={handleNewSession}
            className="w-full"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Session
          </Button>
        )}
        {role === 'coach' && (
          <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">Coach Portal</p>
        )}
        {role === 'admin' && (
          <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider">Admin Portal</p>
        )}
      </div>

      {/* Navigation */}
      <nav className="px-3 py-2 border-b border-gray-700">
        <Link
          href="/dashboard"
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
            ${pathname === '/dashboard' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          {role === 'coach' ? 'Client Sessions' : 'Dashboard'}
        </Link>
        {role === 'admin' && (
          <Link
            href="/documents"
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors mt-1
              ${pathname === '/documents' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Methodology Docs
          </Link>
        )}
        {role === 'coach' && (
          <Link
            href="/coach-documents"
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors mt-1
              ${pathname === '/coach-documents' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Client Documents
          </Link>
        )}
        {role === 'admin' && (
          <Link
            href="/users"
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors mt-1
              ${pathname === '/users' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            Users
          </Link>
        )}
        {role === 'admin' && (
          <Link
            href="/prompts"
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors mt-1
              ${pathname === '/prompts' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Prompt Templates
          </Link>
        )}
      </nav>

      {/* Sessions list — hidden for admins (they use the dashboard client dropdown instead) */}
      {role !== 'admin' && (
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <p className="text-xs text-gray-500 uppercase tracking-wider px-3 mb-2">
          {role === 'coach' ? 'Client Sessions' : 'Recent Sessions'}
        </p>

        {loading ? (
          <div className="flex justify-center py-6">
            <Spinner size="sm" className="text-gray-400" />
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-gray-500 px-3 py-2">
            {role === 'client' ? 'No sessions yet. Start one above!' : 'No sessions found.'}
          </p>
        ) : (
          <ul className="space-y-1">
            {sessions.map((session) => {
              const isActive = pathname === `/chat/${session.id}`;
              return (
                <li key={session.id}>
                  <Link
                    href={`/chat/${session.id}`}
                    className={`block rounded-lg px-3 py-2 text-sm transition-colors
                      ${isActive ? 'bg-blue-700 text-white' : 'text-gray-300 hover:bg-gray-800'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium truncate pr-2">{session.title || 'New Coaching Session'}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full flex-shrink-0 ${statusColors[session.status]}`}>
                        {session.status}
                      </span>
                    </div>
                    {role !== 'client' && session.clientEmail && (
                      <p className="text-xs text-blue-300 truncate">{session.clientEmail}</p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">
                      {new Date(session.updatedAt).toLocaleDateString()}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      )}
    </aside>
  );
}
