'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { documentsApi, DocumentInfo } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

const ACCEPTED = '.pdf,.docx,.xlsx,.txt,.md';

interface UploadState {
  filename: string;
  progress: number; // 0-100
  done: boolean;
  error?: string;
}

export default function DocumentsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const role = user?.role ?? 'client';

  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [replacingId, setReplacingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (role !== 'admin') {
      router.replace('/dashboard');
      return;
    }
    load();
  }, [role]);

  async function load() {
    setLoading(true);
    try {
      const docs = await documentsApi.list();
      setDocuments(docs);
    } catch {
      setError('Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setError(null);
    setSuccessMsg(null);

    const initial: UploadState[] = files.map((f) => ({
      filename: f.name,
      progress: 0,
      done: false,
    }));
    setUploads(initial);

    let successCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        await documentsApi.upload(file, (pct) => {
          setUploads((prev) =>
            prev.map((u, idx) => (idx === i ? { ...u, progress: pct } : u))
          );
        });
        setUploads((prev) =>
          prev.map((u, idx) => (idx === i ? { ...u, progress: 100, done: true } : u))
        );
        successCount++;
      } catch (err: any) {
        const detail = err?.response?.data?.detail || 'Upload failed.';
        setUploads((prev) =>
          prev.map((u, idx) => (idx === i ? { ...u, error: detail } : u))
        );
      }
    }

    if (successCount > 0) {
      setSuccessMsg(
        successCount === files.length
          ? `${successCount} document${successCount > 1 ? 's' : ''} uploaded successfully.`
          : `${successCount} of ${files.length} documents uploaded (see errors above).`
      );
      await load();
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
    // Keep uploads visible briefly then clear
    setTimeout(() => setUploads([]), 4000);
  }

  async function handleReplace(doc: DocumentInfo, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setReplacingId(doc.doc_id);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await documentsApi.replace(doc.doc_id, file);
      setSuccessMsg(`"${file.name}" uploaded — ${result.ingested} chunks indexed.`);
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Replace failed.';
      setError(detail);
    } finally {
      setReplacingId(null);
      const inp = replaceInputRefs.current[doc.doc_id];
      if (inp) inp.value = '';
    }
  }

  async function handleDelete(doc: DocumentInfo) {
    const confirmed = window.confirm(
      `Delete "${doc.filename}" from the knowledge base? This cannot be undone.`
    );
    if (!confirmed) return;
    setDeletingId(doc.doc_id);
    try {
      await documentsApi.remove(doc.doc_id);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== doc.doc_id));
    } catch {
      setError('Failed to delete document.');
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Methodology Knowledge Base</h1>
            <p className="text-gray-500 text-sm mt-1">
              Upload coaching methodology documents (PDF, DOCX, XLSX, TXT, MD) that the AI coach
              will reference during sessions.
            </p>
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              multiple
              className="hidden"
              onChange={handleUpload}
            />
            <Button onClick={() => fileInputRef.current?.click()} size="md">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                />
              </svg>
              Upload Documents
            </Button>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex justify-between">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">
              Dismiss
            </button>
          </div>
        )}
        {successMsg && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700 flex justify-between">
            {successMsg}
            <button onClick={() => setSuccessMsg(null)} className="ml-2 underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Upload progress bars */}
        {uploads.length > 0 && (
          <div className="mb-6 space-y-2">
            {uploads.map((u, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700 truncate max-w-xs">{u.filename}</span>
                  <span
                    className={
                      u.error
                        ? 'text-red-600'
                        : u.done
                        ? 'text-green-600'
                        : 'text-blue-600'
                    }
                  >
                    {u.error ? 'Error' : u.done ? 'Done' : `${u.progress}%`}
                  </span>
                </div>
                {u.error ? (
                  <p className="text-xs text-red-600">{u.error}</p>
                ) : (
                  <div className="w-full bg-gray-200 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full transition-all ${
                        u.done ? 'bg-green-500' : 'bg-blue-500'
                      }`}
                      style={{ width: `${u.progress}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Content */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="h-20 w-20 rounded-full bg-blue-50 flex items-center justify-center mb-6">
              <svg
                className="h-10 w-10 text-blue-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-700 mb-2">No documents yet</h2>
            <p className="text-gray-500 text-sm mb-6 max-w-xs">
              Upload coaching resources, frameworks, or reference materials for the AI to use.
            </p>
            <Button onClick={() => fileInputRef.current?.click()}>Upload First Document</Button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Filename</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Chunks</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Uploaded</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {documents.map((doc, idx) => (
                  <tr key={doc.doc_id} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-5 py-3 font-medium text-gray-800">{doc.filename}</td>
                    <td className="px-5 py-3 text-gray-500">{doc.chunk_count}</td>
                    <td className="px-5 py-3 text-gray-400">
                      {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {/* Download */}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-blue-600 hover:bg-blue-50 hover:text-blue-700"
                          onClick={() => documentsApi.download(doc.doc_id, doc.filename)}
                          title="Download original file"
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
                          title="Replace with a new file"
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
                          title="Remove from knowledge base"
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
        )}
      </div>
    </div>
  );
}

