'use client';

import { ChangeEvent, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { coachDocumentsApi, usersApi, CoachDocumentInfo } from '@/lib/api';
import { UserProfile } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

const ACCEPTED = '.pdf,.docx,.txt,.md';

export default function CoachDocumentsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const role = user?.role ?? 'client';

  const [clients, setClients] = useState<UserProfile[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string>('');
  const [documents, setDocuments] = useState<CoachDocumentInfo[]>([]);
  const [loadingClients, setLoadingClients] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
  const [replacingId, setReplacingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const uploadInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (role !== 'coach') {
      router.replace('/dashboard');
      return;
    }
    loadClients();
  }, [role]);

  async function loadClients() {
    setLoadingClients(true);
    try {
      const data = await usersApi.listMyClients();
      setClients(data);
    } catch {
      setError('Failed to load your assigned clients.');
    } finally {
      setLoadingClients(false);
    }
  }

  async function loadDocuments(clientId: string) {
    setLoadingDocs(true);
    setError(null);
    try {
      const docs = await coachDocumentsApi.list(clientId || undefined);
      setDocuments(docs);
    } catch {
      setError('Failed to load documents.');
    } finally {
      setLoadingDocs(false);
    }
  }

  function handleClientChange(e: ChangeEvent<HTMLSelectElement>) {
    const id = e.target.value;
    setSelectedClientId(id);
    setDocuments([]);
    if (id) loadDocuments(id);
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0 || !selectedClientId) return;
    setUploadProgress({ done: 0, total: files.length });
    setError(null);
    setSuccessMsg(null);
    const errors: string[] = [];
    let totalChunks = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const result = await coachDocumentsApi.upload(file, selectedClientId);
        totalChunks += result.ingested ?? 0;
      } catch (err: any) {
        const detail = err?.response?.data?.detail || `Failed to upload "${file.name}".`;
        errors.push(detail);
      }
      setUploadProgress({ done: i + 1, total: files.length });
    }
    await loadDocuments(selectedClientId);
    if (errors.length === 0) {
      setSuccessMsg(
        files.length === 1
          ? `"${files[0].name}" uploaded — ${totalChunks} chunks indexed.`
          : `${files.length} documents uploaded — ${totalChunks} chunks indexed.`
      );
    } else {
      setError(errors.join(' | '));
    }
    setUploadProgress(null);
    if (uploadInputRef.current) uploadInputRef.current.value = '';
  }

  async function handleReplace(doc: CoachDocumentInfo, e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setReplacingId(doc.doc_id);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await coachDocumentsApi.replace(doc.doc_id, file);
      setSuccessMsg(`"${doc.filename}" replaced with "${file.name}" — ${result.ingested} chunks indexed.`);
      await loadDocuments(selectedClientId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Replace failed.';
      setError(detail);
    } finally {
      setReplacingId(null);
      const ref = replaceInputRefs.current[doc.doc_id];
      if (ref) ref.value = '';
    }
  }

  async function handleDownload(doc: CoachDocumentInfo) {
    setDownloadingId(doc.doc_id);
    try {
      await coachDocumentsApi.download(doc.doc_id, doc.filename);
    } catch {
      setError(`Failed to download "${doc.filename}".`);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(doc: CoachDocumentInfo) {
    const confirmed = window.confirm(
      `Delete "${doc.filename}" from the knowledge base? This cannot be undone.`
    );
    if (!confirmed) return;
    setDeletingId(doc.doc_id);
    try {
      await coachDocumentsApi.remove(doc.doc_id);
      setDocuments((prev: CoachDocumentInfo[]) => prev.filter((d: CoachDocumentInfo) => d.doc_id !== doc.doc_id));
      setSuccessMsg(`"${doc.filename}" deleted.`);
    } catch {
      setError('Failed to delete document.');
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Client Documents</h1>
            <p className="text-gray-500 text-sm mt-1">
              Upload past conversation notes and documents (PDF, Word .docx, .txt, .md) for your assigned clients.
              These are used by the AI during that client's sessions.
            </p>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex justify-between">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
          </div>
        )}
        {successMsg && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700 flex justify-between">
            {successMsg}
            <button onClick={() => setSuccessMsg(null)} className="ml-2 underline">Dismiss</button>
          </div>
        )}

        {/* Client selector */}
        <div className="bg-white rounded-xl border border-gray-200 px-6 py-5 mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Select Client
          </label>
          {loadingClients ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner size="sm" /> Loading your clients…
            </div>
          ) : clients.length === 0 ? (
            <p className="text-sm text-gray-500">No clients are assigned to you yet.</p>
          ) : (
            <div className="flex flex-col sm:flex-row gap-3">
              <select
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={selectedClientId}
                onChange={handleClientChange}
              >
                <option value="">— Choose a client —</option>
                {clients.map((c: UserProfile) => (
                  <option key={c.id} value={c.id}>
                    {c.email}
                  </option>
                ))}
              </select>

              {selectedClientId && (
                <>
                  <input
                    ref={uploadInputRef}
                    type="file"
                    accept={ACCEPTED}
                    multiple
                    className="hidden"
                    onChange={handleUpload}
                  />
                  <Button
                    onClick={() => uploadInputRef.current?.click()}
                    loading={uploadProgress !== null}
                    size="md"
                    disabled={!selectedClientId}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    {uploadProgress
                      ? `Uploading ${uploadProgress.done}/${uploadProgress.total}…`
                      : 'Upload Documents'}
                  </Button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Documents table */}
        {selectedClientId && (
          loadingDocs ? (
            <div className="flex justify-center py-16">
              <Spinner size="lg" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="h-20 w-20 rounded-full bg-blue-50 flex items-center justify-center mb-6">
                <svg className="h-10 w-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">No documents yet</h2>
              <p className="text-gray-500 text-sm mb-6 max-w-xs">
                Upload past conversation notes or session summaries for this client.
              </p>
              <Button onClick={() => uploadInputRef.current?.click()} loading={uploadProgress !== null}>
                Upload First Document
              </Button>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-5 py-3 font-semibold text-gray-600">Filename</th>
                    <th className="text-left px-5 py-3 font-semibold text-gray-600">Client</th>
                    <th className="text-left px-5 py-3 font-semibold text-gray-600">Chunks</th>
                    <th className="text-left px-5 py-3 font-semibold text-gray-600">Uploaded</th>
                    <th className="px-5 py-3 text-right font-semibold text-gray-600">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc, idx) => (
                    <tr key={doc.doc_id} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-5 py-3 font-medium text-gray-800">{doc.filename}</td>
                      <td className="px-5 py-3 text-gray-500">{doc.client_email ?? doc.client_id}</td>
                      <td className="px-5 py-3 text-gray-500">{doc.chunk_count}</td>
                      <td className="px-5 py-3 text-gray-400">
                        {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {/* Download */}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-blue-600 hover:bg-blue-50 hover:text-blue-700"
                            onClick={() => handleDownload(doc)}
                            loading={downloadingId === doc.doc_id}
                          >
                            Download
                          </Button>

                          {/* Replace */}
                          <input
                            ref={(el) => { replaceInputRefs.current[doc.doc_id] = el; }}
                            type="file"
                            accept={ACCEPTED}
                            className="hidden"
                            onChange={(e) => handleReplace(doc, e)}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-amber-600 hover:bg-amber-50 hover:text-amber-700"
                            onClick={() => replaceInputRefs.current[doc.doc_id]?.click()}
                            loading={replacingId === doc.doc_id}
                          >
                            Replace
                          </Button>

                          {/* Delete */}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => handleDelete(doc)}
                            loading={deletingId === doc.doc_id}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {/* Prompt if no client selected yet */}
        {!selectedClientId && !loadingClients && clients.length > 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center text-gray-400">
            <svg className="h-12 w-12 mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p className="text-sm">Select a client above to view or upload documents.</p>
          </div>
        )}
      </div>
    </div>
  );
}
