import axios, { AxiosInstance } from 'axios';
import { useAuthStore } from '@/store/auth';
import { Session, Message, UserProfile, PromptsConfig } from '@/types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
  });

  client.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        useAuthStore.getState().clearAuth();
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );

  return client;
}

export const apiClient = createApiClient();

// ─── Mappers ──────────────────────────────────────────────────────────────────

function mapSession(raw: any): Session {
  return {
    id: raw.id,
    title: raw.title,
    status: raw.status,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    clientEmail: raw.client_email ?? undefined,
    clientId: raw.client_id ?? undefined,
    coachId: raw.coach_id ?? undefined,
    lastMessage: raw.last_message ?? undefined,
  };
}

function mapUser(raw: any): UserProfile {
  return {
    id: raw.id,
    email: raw.email,
    role: raw.role,
    tenantId: raw.tenant_id,
    coachId: raw.coach_id ?? undefined,
    createdAt: raw.created_at,
  };
}

// ─── Sessions API ─────────────────────────────────────────────────────────────

export const sessionsApi = {
  list: async (): Promise<Session[]> => {
    const res = await apiClient.get<any[]>('/api/v1/sessions');
    return res.data.map(mapSession);
  },
  listByClient: async (clientId: string): Promise<Session[]> => {
    const res = await apiClient.get<any[]>('/api/v1/sessions', { params: { client_id: clientId } });
    return res.data.map(mapSession);
  },
  create: async (payload?: { title?: string }): Promise<Session> => {
    const res = await apiClient.post<any>('/api/v1/sessions', payload ?? {});
    return mapSession(res.data);
  },
  get: async (id: string): Promise<Session> => {
    const res = await apiClient.get<any>(`/api/v1/sessions/${id}`);
    return mapSession(res.data);
  },
  update: async (id: string, payload: { title?: string; status?: string; coach_id?: string | null }): Promise<Session> => {
    const res = await apiClient.patch<any>(`/api/v1/sessions/${id}`, payload);
    return mapSession(res.data);
  },
  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/sessions/${id}`);
  },
};

// ─── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.post('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};

// ─── Messages API ─────────────────────────────────────────────────────────────

function mapMessage(raw: any): Message {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    role: raw.role,
    content: raw.content,
    createdAt: raw.created_at ?? raw.createdAt,
  };
}

export const messagesApi = {
  list: async (sessionId: string): Promise<Message[]> => {
    const res = await apiClient.get<any[]>(`/api/v1/sessions/${sessionId}/messages`);
    return res.data.map(mapMessage);
  },
};

// ─── Users API ────────────────────────────────────────────────────────────────

export const usersApi = {
  listMyClients: async (): Promise<UserProfile[]> => {
    const res = await apiClient.get<any[]>('/api/v1/users/my-clients');
    return res.data.map(mapUser);
  },
  listCoaches: async (): Promise<UserProfile[]> => {
    const res = await apiClient.get<any[]>('/api/v1/users/coaches');
    return res.data.map(mapUser);
  },
  list: async (): Promise<UserProfile[]> => {
    const res = await apiClient.get<any[]>('/api/v1/users');
    return res.data.map(mapUser);
  },
  assignCoach: async (userId: string, coachId: string | null): Promise<UserProfile> => {
    const res = await apiClient.patch<any>(`/api/v1/users/${userId}`, { coach_id: coachId });
    return mapUser(res.data);
  },
  listClientsForCoach: async (coachId: string): Promise<UserProfile[]> => {
    const res = await apiClient.get<any[]>(`/api/v1/users/coaches/${coachId}/clients`);
    return res.data.map(mapUser);
  },
  unassignCoach: async (userId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/users/${userId}/coach`);
  },
};

// ─── Documents API (admin — methodology docs) ────────────────────────────────

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  chunk_count: number;
  uploaded_at?: string;
}

export const documentsApi = {
  list: async (): Promise<DocumentInfo[]> => {
    const res = await apiClient.get<DocumentInfo[]>('/api/v1/embeddings/documents');
    return res.data;
  },
  upload: async (
    file: File,
    onProgress?: (pct: number) => void,
  ): Promise<{ ingested: number; collection: string }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await apiClient.post('/api/v1/embeddings/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (onProgress && evt.total) onProgress(Math.round((evt.loaded * 100) / evt.total));
      },
    });
    return res.data;
  },
  download: async (docId: string, filename: string): Promise<void> => {
    const res = await apiClient.get(`/api/v1/embeddings/documents/${docId}/download`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
  replace: async (
    docId: string,
    file: File,
    onProgress?: (pct: number) => void,
  ): Promise<{ ingested: number; collection: string }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await apiClient.put(`/api/v1/embeddings/documents/${docId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (onProgress && evt.total) onProgress(Math.round((evt.loaded * 100) / evt.total));
      },
    });
    return res.data;
  },
  remove: async (docId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/embeddings/documents/${docId}`);
  },
};

// ─── Coach Documents API (coach — client conversation docs) ───────────────────

export interface CoachDocumentInfo {
  doc_id: string;
  filename: string;
  client_id: string;
  client_email?: string;
  chunk_count: number;
  uploaded_at?: string;
}

// ─── Prompts API (admin — prompt templates) ─────────────────────────────────

function mapPrompts(raw: any): PromptsConfig {
  return {
    coachSystemPrompt: raw.coach_system_prompt,
    guardrails: {
      do: raw.guardrails_do,
      doNot: raw.guardrails_do_not,
    },
    intake: { extractionPrompt: raw.intake_extraction_prompt },
    reflection: { summaryPrompt: raw.reflection_summary_prompt },
    escalation: {
      message: raw.escalation_message,
      keywords: raw.escalation_keywords,
    },
  };
}

export const promptsApi = {
  get: async (): Promise<PromptsConfig> => {
    const res = await apiClient.get<any>('/api/v1/prompts');
    return mapPrompts(res.data);
  },
  update: async (config: PromptsConfig): Promise<PromptsConfig> => {
    const payload = {
      coach_system_prompt: config.coachSystemPrompt,
      guardrails_do: config.guardrails.do,
      guardrails_do_not: config.guardrails.doNot,
      intake_extraction_prompt: config.intake.extractionPrompt,
      reflection_summary_prompt: config.reflection.summaryPrompt,
      escalation_message: config.escalation.message,
      escalation_keywords: config.escalation.keywords,
    };
    const res = await apiClient.put<any>('/api/v1/prompts', payload);
    return mapPrompts(res.data);
  },
};

// ─── Coach Documents API (coach — client conversation docs) ───────────────────

export const coachDocumentsApi = {
  list: async (clientId?: string): Promise<CoachDocumentInfo[]> => {
    const params = clientId ? { client_id: clientId } : {};
    const res = await apiClient.get<CoachDocumentInfo[]>('/api/v1/embeddings/coach/documents', { params });
    return res.data;
  },
  upload: async (file: File, clientId: string): Promise<{ ingested: number; collection: string }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('client_id', clientId);
    const res = await apiClient.post('/api/v1/embeddings/coach/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  download: async (docId: string, filename: string): Promise<void> => {
    const res = await apiClient.get(`/api/v1/embeddings/coach/documents/${docId}/download`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  replace: async (docId: string, file: File): Promise<{ ingested: number; collection: string }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await apiClient.put(`/api/v1/embeddings/coach/documents/${docId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  remove: async (docId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/embeddings/coach/documents/${docId}`);
  },
};
