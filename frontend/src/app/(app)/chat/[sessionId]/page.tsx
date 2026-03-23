'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { sessionsApi } from '@/lib/api';
import { Session } from '@/types';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';

export default function ChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { user } = useAuth();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setLoading(true);
    sessionsApi.get(sessionId)
      .then((s) => { if (!cancelled) setSession(s); })
      .catch((err) => {
        if (cancelled) return;
        const status = err?.response?.status;
        if (status === 404) {
          setError('Session not found.');
        } else if (status === 403) {
          setError('You are not authorized to access this session.');
        } else {
          setError('Failed to load session. Please try again.');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 font-medium">{error || 'Session not found'}</p>
          <a href="/dashboard" className="text-blue-600 text-sm underline mt-2 inline-block">
            Back to dashboard
          </a>
        </div>
      </div>
    );
  }

  async function handleCompleteSession() {
    if (!session) return;
    const confirmed = window.confirm('Mark this session as completed? No further coaching messages can be sent.');
    if (!confirmed) return;
    setCompleting(true);
    try {
      const updated = await sessionsApi.update(session.id, { status: 'completed' });
      setSession(updated);
      window.dispatchEvent(new CustomEvent('sessionUpdated', { detail: updated }));
    } catch {
      setError('Failed to complete session. Please try again.');
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-gray-900 truncate">{session.title || 'Coaching Session'}</h2>
          <p className="text-xs text-gray-500">
            Started {new Date(session.createdAt).toLocaleDateString()} •{' '}
            <span className={session.status === 'active' ? 'text-green-600' : 'text-gray-500'}>
              {session.status}
            </span>
          </p>
        </div>
        {user?.role === 'client' && session.status === 'active' && (
          <Button
            variant="secondary"
            size="sm"
            loading={completing}
            onClick={handleCompleteSession}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Complete Session
          </Button>
        )}
        {session.status === 'completed' && (
          <span className="text-xs px-3 py-1 bg-gray-100 text-gray-500 rounded-full border border-gray-200">
            Session completed
          </span>
        )}
      </div>

      {/* Chat window */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <ChatWindow
          sessionId={sessionId}
          readOnly={session.status !== 'active' || user?.role !== 'client'}
        />
      </div>
    </div>
  );
}
