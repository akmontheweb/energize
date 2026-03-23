'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Session, UserProfile } from '@/types';
import { sessionsApi, usersApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/hooks/useAuth';

const statusColors: Record<Session['status'], string> = {
  active: 'bg-green-100 text-green-700 border-green-200',
  completed: 'bg-gray-100 text-gray-600 border-gray-200',
  escalated: 'bg-red-100 text-red-700 border-red-200',
  archived: 'bg-yellow-100 text-yellow-700 border-yellow-200',
};

function SessionCard({
  session,
  onClick,
  onRename,
  onClose,
  onDelete,
  closing,
  deleting,
}: {
  session: Session;
  onClick: () => void;
  onRename: () => void;
  onClose: () => void;
  onDelete: () => void;
  closing: boolean;
  deleting: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:border-blue-300 hover:shadow-md transition-all duration-200 group">
      <button onClick={onClick} className="w-full text-left">
        <div className="flex items-start justify-between mb-3">
          <h3 className="font-semibold text-gray-900 group-hover:text-blue-700 transition-colors line-clamp-1 pr-3">
            {session.title || 'New Coaching Session'}
          </h3>
          <span className={`text-xs px-2 py-1 rounded-full border flex-shrink-0 ${statusColors[session.status]}`}>
            {session.status}
          </span>
        </div>

        {session.clientEmail && (
          <p className="text-xs text-blue-600 font-medium mb-2">{session.clientEmail}</p>
        )}

        {session.lastMessage && (
          <p className="text-xs text-gray-500 line-clamp-2 mb-3 leading-relaxed">{session.lastMessage}</p>
        )}

        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Created {new Date(session.createdAt).toLocaleDateString()}</span>
          <span>Updated {new Date(session.updatedAt).toLocaleDateString()}</span>
        </div>
      </button>

      <div className="mt-4 pt-3 border-t border-gray-100 flex justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="text-gray-700 hover:bg-gray-100"
          onClick={onRename}
          disabled={session.status === 'completed'}
        >
          Rename
        </Button>
        {session.status === 'active' && (
          <Button
            variant="ghost"
            size="sm"
            className="text-green-700 hover:bg-green-50 hover:text-green-800"
            onClick={onClose}
            loading={closing}
          >
            Complete
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="text-red-600 hover:bg-red-50 hover:text-red-700"
          onClick={onDelete}
          loading={deleting}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

function ReadOnlySessionCard({ session, onClick }: { session: Session; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="bg-white rounded-xl border border-gray-200 p-5 hover:border-blue-300 hover:shadow-md transition-all duration-200 group text-left w-full"
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-semibold text-gray-900 group-hover:text-blue-700 transition-colors line-clamp-1 pr-3">
          {session.title || 'Coaching Session'}
        </h3>
        <span className={`text-xs px-2 py-1 rounded-full border flex-shrink-0 ${statusColors[session.status]}`}>
          {session.status}
        </span>
      </div>
      {session.clientEmail && (
        <p className="text-xs text-blue-600 font-medium mb-2">Client: {session.clientEmail}</p>
      )}
      {session.lastMessage && (
        <p className="text-xs text-gray-500 line-clamp-2 mb-3 leading-relaxed">{session.lastMessage}</p>
      )}
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>Created {new Date(session.createdAt).toLocaleDateString()}</span>
        <span>Updated {new Date(session.updatedAt).toLocaleDateString()}</span>
      </div>
    </button>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const role = user?.role ?? 'client';
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [closingSessionId, setClosingSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Admin-only: client list + selected client
  const [clients, setClients] = useState<UserProfile[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (role === 'admin') {
      // Load the client list; don't fetch sessions yet
      usersApi.list()
        .then((all) => { if (!cancelled) setClients(all.filter((u) => u.role === 'client')); })
        .catch(() => { if (!cancelled) setError('Failed to load client list.'); })
        .finally(() => { if (!cancelled) setLoading(false); });
    } else {
      setLoading(true);
      sessionsApi.list()
        .then((data) => { if (!cancelled) setSessions(data); })
        .catch(() => { if (!cancelled) setError('Failed to load sessions. Please try again.'); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [role]);

  async function handleClientSelect(clientId: string) {
    setSelectedClientId(clientId);
    if (!clientId) { setSessions([]); return; }
    setLoadingSessions(true);
    setError(null);
    try {
      const data = await sessionsApi.listByClient(clientId);
      setSessions(data);
    } catch {
      setError('Failed to load sessions for this client.');
    } finally {
      setLoadingSessions(false);
    }
  };

  async function handleNewSession() {
    const titleInput = window.prompt('Enter a session name', 'My Coaching Session');
    if (titleInput === null) return;

    const title = titleInput.trim();
    setCreating(true);
    try {
      const session = await sessionsApi.create({ title: title || 'New Coaching Session' });
      window.dispatchEvent(new CustomEvent('sessionCreated', { detail: session }));
      router.push(`/chat/${session.id}`);
    } catch {
      setError('Failed to create session.');
    } finally {
      setCreating(false);
    }
  }

  async function handleRenameSession(session: Session) {
    const currentTitle = session.title || 'New Coaching Session';
    const titleInput = window.prompt('Rename session', currentTitle);
    if (titleInput === null) return;

    const nextTitle = titleInput.trim();
    if (!nextTitle) {
      setError('Session name cannot be empty.');
      return;
    }

    try {
      const updated = await sessionsApi.update(session.id, { title: nextTitle });
      setSessions((prev) => prev.map((s) => (s.id === session.id ? updated : s)));
    } catch {
      setError('Failed to rename session. Please try again.');
    }
  }

  async function handleCloseSession(sessionId: string) {
    const confirmed = window.confirm('Mark this session as completed? You can still view it but no further coaching messages can be sent.');
    if (!confirmed) return;

    setClosingSessionId(sessionId);
    try {
      const updated = await sessionsApi.update(sessionId, { status: 'completed' });
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? updated : s)));
      window.dispatchEvent(new CustomEvent('sessionUpdated', { detail: updated }));
    } catch {
      setError('Failed to complete session. Please try again.');
    } finally {
      setClosingSessionId(null);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    const confirmed = window.confirm('Delete this session and all its messages? This cannot be undone.');
    if (!confirmed) return;

    setDeletingSessionId(sessionId);
    try {
      await sessionsApi.remove(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      window.dispatchEvent(new CustomEvent('sessionDeleted', { detail: { id: sessionId } }));
    } catch {
      setError('Failed to delete session. Please try again.');
    } finally {
      setDeletingSessionId(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {role === 'coach' ? 'Client Sessions' : role === 'admin' ? 'Session Explorer' : 'My Sessions'}
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              {role === 'admin'
                ? selectedClientId
                  ? `${sessions.length} session${sessions.length !== 1 ? 's' : ''} for ${clients.find((c) => c.id === selectedClientId)?.email ?? 'client'}`
                  : 'Select a client to view their sessions'
                : `${sessions.length} coaching session${sessions.length !== 1 ? 's' : ''}`
              }
            </p>
          </div>
          {role === 'client' && (
            <Button onClick={handleNewSession} loading={creating} size="md">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Session
            </Button>
          )}
          {role === 'admin' && (
            <Button variant="secondary" size="md" onClick={() => router.push('/users')}>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              Manage Client Assignments
            </Button>
          )}
        </div>

        {role === 'admin' && (
          <div className="mb-6">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Spinner size="sm" />
                Loading clients&hellip;
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <label htmlFor="client-select" className="text-sm font-medium text-gray-700 whitespace-nowrap">
                  Select client
                </label>
                <select
                  id="client-select"
                  value={selectedClientId ?? ''}
                  onChange={(e) => handleClientSelect(e.target.value)}
                  className="block w-72 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">— Select a client —</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>{c.email}</option>
                  ))}
                </select>
                {clients.length === 0 && (
                  <span className="text-sm text-gray-400">No clients found in this tenant.</span>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
          </div>
        )}

        {loading && role !== 'admin' ? (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : loadingSessions ? (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : role === 'admin' && !selectedClientId ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="h-20 w-20 rounded-full bg-blue-50 flex items-center justify-center mb-6">
              <svg className="h-10 w-10 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-700 mb-2">No client selected</h2>
            <p className="text-gray-500 text-sm max-w-xs">
              Choose a client from the dropdown above to browse their coaching sessions.
            </p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="h-20 w-20 rounded-full bg-blue-50 flex items-center justify-center mb-6">
              <svg className="h-10 w-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-700 mb-2">
              {role === 'client' ? 'No sessions yet' : 'No sessions found'}
            </h2>
            <p className="text-gray-500 text-sm mb-6 max-w-xs">
              {role === 'client'
                ? 'Start your first coaching session and begin your personal growth journey.'
                : 'No client sessions are assigned to you yet.'}
            </p>
            {role === 'client' && (
              <Button onClick={handleNewSession} loading={creating}>
                Start First Session
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sessions.map((session) => (
              role === 'client' ? (
                <SessionCard
                  key={session.id}
                  session={session}
                  onClick={() => router.push(`/chat/${session.id}`)}
                  onRename={() => handleRenameSession(session)}
                  onClose={() => handleCloseSession(session.id)}
                  onDelete={() => handleDeleteSession(session.id)}
                  closing={closingSessionId === session.id}
                  deleting={deletingSessionId === session.id}
                />
              ) : (
                <ReadOnlySessionCard
                  key={session.id}
                  session={session}
                  onClick={() => router.push(`/chat/${session.id}`)}
                />
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
