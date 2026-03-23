'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usersApi } from '@/lib/api';
import { UserProfile } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { Spinner } from '@/components/ui/Spinner';

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const role = user?.role ?? 'client';

  const [users, setUsers] = useState<UserProfile[]>([]);
  const [coaches, setCoaches] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (role !== 'admin') {
      router.replace('/dashboard');
      return;
    }
    Promise.all([usersApi.list(), usersApi.listCoaches()])
      .then(([allUsers, coachList]) => {
        setUsers(allUsers);
        setCoaches(coachList);
      })
      .catch(() => setError('Failed to load users.'))
      .finally(() => setLoading(false));
  }, [role]);

  async function handleAssignCoach(userId: string, coachId: string) {
    setSavingId(userId);
    setError(null);
    try {
      const updated = await usersApi.assignCoach(userId, coachId || null);
      setUsers((prev: UserProfile[]) => prev.map((u: UserProfile) => (u.id === userId ? { ...u, coachId: updated.coachId } : u)));
    } catch {
      setError('Failed to update coach assignment.');
    } finally {
      setSavingId(null);
    }
  }

  async function handleUnassignCoach(userId: string) {
    setSavingId(userId);
    setError(null);
    try {
      await usersApi.unassignCoach(userId);
      setUsers((prev: UserProfile[]) => prev.map((u: UserProfile) => (u.id === userId ? { ...u, coachId: undefined } : u)));
    } catch {
      setError('Failed to remove coach assignment.');
    } finally {
      setSavingId(null);
    }
  }

  const roleBadge = (r: string) => {
    const colors: Record<string, string> = {
      admin: 'bg-purple-100 text-purple-700',
      coach: 'bg-blue-100 text-blue-700',
      client: 'bg-green-100 text-green-700',
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[r] ?? 'bg-gray-100 text-gray-600'}`}>
        {r}
      </span>
    );
  };

  const clients = users.filter((u: UserProfile) => u.role === 'client');
  const coachAssignments = coaches.map((coach) => ({
    coach,
    clientCount: clients.filter((client: UserProfile) => client.coachId === coach.id).length,
  }));

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-gray-500 text-sm mt-1">
            Assign coaches to clients. Multiple clients can share one coach.
          </p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex justify-between">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : (
          <>
            <section className="mb-10">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Coach Workload</h2>
              {coaches.length === 0 ? (
                <p className="text-gray-500 text-sm">No coaches found.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {coachAssignments.map(({ coach, clientCount }) => (
                    <div key={coach.id} className="bg-white rounded-xl border border-gray-200 p-5">
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="min-w-0">
                          <p className="font-semibold text-gray-900 truncate">{coach.email}</p>
                          <p className="text-xs text-gray-400 truncate">{coach.id}</p>
                        </div>
                        {roleBadge(coach.role)}
                      </div>
                      <p className="text-sm text-gray-500">Assigned clients</p>
                      <p className="text-3xl font-bold text-blue-700 mt-1">{clientCount}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Client-Coach Assignments */}
            <section className="mb-10">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Client — Coach Assignments</h2>
              {clients.length === 0 ? (
                <p className="text-gray-500 text-sm">No clients found.</p>
              ) : (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="text-left px-5 py-3 font-semibold text-gray-600">Client</th>
                        <th className="text-left px-5 py-3 font-semibold text-gray-600">Assigned Coach</th>
                        <th className="px-5 py-3 font-semibold text-gray-600 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clients.map((client, idx) => {
                        const assignedCoach = coaches.find((c) => c.id === client.coachId);
                        const isSaving = savingId === client.id;
                        return (
                          <tr key={client.id} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                            <td className="px-5 py-3">
                              <p className="font-medium text-gray-800">{client.email}</p>
                              <p className="text-xs text-gray-400">{client.id}</p>
                            </td>
                            <td className="px-5 py-3">
                              <select
                                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[200px]"
                                value={client.coachId ?? ''}
                                disabled={isSaving || coaches.length === 0}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  if (val === '') {
                                    handleUnassignCoach(client.id);
                                  } else {
                                    handleAssignCoach(client.id, val);
                                  }
                                }}
                              >
                                <option value="">— Unassigned —</option>
                                {coaches.map((c) => (
                                  <option key={c.id} value={c.id}>{c.email}</option>
                                ))}
                              </select>
                              {coaches.length === 0 && (
                                <p className="text-xs text-gray-400 mt-1">No coaches available in this tenant.</p>
                              )}
                            </td>
                            <td className="px-5 py-3 text-right text-gray-400 text-xs">
                              {isSaving ? (
                                <Spinner size="sm" />
                              ) : assignedCoach ? (
                                <span className="text-green-600 font-medium">✓ Saved</span>
                              ) : (
                                <span>—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* All Users overview */}
            <section>
              <h2 className="text-lg font-semibold text-gray-800 mb-4">All Users</h2>
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left px-5 py-3 font-semibold text-gray-600">Email</th>
                      <th className="text-left px-5 py-3 font-semibold text-gray-600">Role</th>
                      <th className="text-left px-5 py-3 font-semibold text-gray-600">Joined</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u, idx) => (
                      <tr key={u.id} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="px-5 py-3 font-medium text-gray-800">{u.email}</td>
                        <td className="px-5 py-3">{roleBadge(u.role)}</td>
                        <td className="px-5 py-3 text-gray-400">
                          {new Date(u.createdAt).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
