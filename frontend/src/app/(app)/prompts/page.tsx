'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { promptsApi } from '@/lib/api';
import { PromptsConfig } from '@/types';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        {description && <p className="text-sm text-gray-500 mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  );
}

function PlaceholderHint({ vars }: { vars: string[] }) {
  return (
    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">
      Available placeholders:{' '}
      {vars.map((v) => (
        <code key={v} className="font-mono bg-amber-100 px-1 rounded mx-0.5">{`{${v}}`}</code>
      ))}
    </p>
  );
}

function EditableList({
  items,
  placeholder,
  onChange,
}: {
  items: string[];
  placeholder?: string;
  onChange: (items: string[]) => void;
}) {
  function update(idx: number, value: string) {
    const next = [...items];
    next[idx] = value;
    onChange(next);
  }

  function remove(idx: number) {
    onChange(items.filter((_, i) => i !== idx));
  }

  function add() {
    onChange([...items, '']);
  }

  return (
    <div className="space-y-2">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <input
            type="text"
            value={item}
            placeholder={placeholder}
            onChange={(e) => update(idx, e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => remove(idx)}
            aria-label="Remove item"
            className="p-1.5 text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 mt-1"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Add item
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PromptsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const role = user?.role ?? 'client';

  const [config, setConfig] = useState<PromptsConfig | null>(null);
  const [savedJson, setSavedJson] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (role !== 'admin') {
      router.replace('/dashboard');
      return;
    }
    promptsApi
      .get()
      .then((data) => {
        setConfig(data);
        setSavedJson(JSON.stringify(data));
      })
      .catch(() => setError('Failed to load prompt templates.'))
      .finally(() => setLoading(false));
  }, [role]);

  const isDirty = config !== null && JSON.stringify(config) !== savedJson;

  async function handleSave() {
    if (!config) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await promptsApi.update(config);
      setConfig(updated);
      setSavedJson(JSON.stringify(updated));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } catch {
      setError('Failed to save prompt templates. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!config) return null;

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Prompt Templates</h1>
            <p className="text-sm text-gray-500 mt-1">
              Manage the AI coaching prompts stored in the database. Changes take effect
              immediately for all new sessions.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            loading={saving}
            disabled={!isDirty || saving}
          >
            Save Changes
          </Button>
        </div>

        {/* Status banners */}
        {isDirty && !saving && (
          <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-2.5 text-sm text-yellow-800">
            You have unsaved changes.
          </div>
        )}
        {success && (
          <div className="mb-4 bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm text-green-800">
            Prompt templates saved successfully.
          </div>
        )}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex justify-between items-start">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="ml-4 underline flex-shrink-0">
              Dismiss
            </button>
          </div>
        )}

        {/* Sections */}
        <div className="space-y-6">
          {/* 1 — Coach System Prompt */}
          <SectionCard
            title="Coach System Prompt"
            description="Core persona and behaviour instructions sent to the AI at the start of every session."
          >
            <textarea
              rows={12}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              value={config.coachSystemPrompt}
              onChange={(e) => setConfig({ ...config, coachSystemPrompt: e.target.value })}
            />
          </SectionCard>

          {/* 2 — Guardrails Do */}
          <SectionCard
            title="Guardrails — Always Do"
            description="Behaviours the AI coach must always exhibit."
          >
            <EditableList
              items={config.guardrails.do}
              placeholder="Behaviour the coach must always do…"
              onChange={(items) =>
                setConfig({ ...config, guardrails: { ...config.guardrails, do: items } })
              }
            />
          </SectionCard>

          {/* 3 — Guardrails Don't */}
          <SectionCard
            title="Guardrails — Never Do"
            description="Behaviours the AI coach must never exhibit."
          >
            <EditableList
              items={config.guardrails.doNot}
              placeholder="Behaviour the coach must never do…"
              onChange={(items) =>
                setConfig({ ...config, guardrails: { ...config.guardrails, doNot: items } })
              }
            />
          </SectionCard>

          {/* 4 — Intake Extraction Prompt */}
          <SectionCard
            title="Intake Extraction Prompt"
            description="Used to extract the client's goals from the opening conversation."
          >
            <PlaceholderHint vars={['conversation']} />
            <textarea
              rows={7}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              value={config.intake.extractionPrompt}
              onChange={(e) =>
                setConfig({ ...config, intake: { extractionPrompt: e.target.value } })
              }
            />
          </SectionCard>

          {/* 5 — Reflection Summary Prompt */}
          <SectionCard
            title="Reflection Summary Prompt"
            description="Used to generate a session summary when a session ends."
          >
            <PlaceholderHint vars={['goals', 'transcript']} />
            <textarea
              rows={9}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              value={config.reflection.summaryPrompt}
              onChange={(e) =>
                setConfig({ ...config, reflection: { summaryPrompt: e.target.value } })
              }
            />
          </SectionCard>

          {/* 6 — Escalation Message */}
          <SectionCard
            title="Escalation Message"
            description="Shown to users when a crisis keyword is detected in the conversation."
          >
            <textarea
              rows={5}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              value={config.escalation.message}
              onChange={(e) =>
                setConfig({
                  ...config,
                  escalation: { ...config.escalation, message: e.target.value },
                })
              }
            />
          </SectionCard>

          {/* 7 — Escalation Keywords */}
          <SectionCard
            title="Escalation Keywords"
            description="Words or phrases that trigger the escalation protocol."
          >
            <EditableList
              items={config.escalation.keywords}
              placeholder="Trigger word or phrase…"
              onChange={(items) =>
                setConfig({
                  ...config,
                  escalation: { ...config.escalation, keywords: items },
                })
              }
            />
          </SectionCard>
        </div>

        {/* Footer save button */}
        <div className="mt-8 flex justify-end">
          <Button
            variant="primary"
            onClick={handleSave}
            loading={saving}
            disabled={!isDirty || saving}
          >
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
