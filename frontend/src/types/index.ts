export interface User {
  id: string;
  email: string;
  name: string;
  preferredUsername: string;
  role?: 'client' | 'coach' | 'admin';
}

export interface Session {
  id: string;
  title?: string;
  status: 'active' | 'completed' | 'escalated' | 'archived';
  createdAt: string;
  updatedAt: string;
  lastMessage?: string;
  clientEmail?: string;
  clientId?: string;
  coachId?: string;
}

export interface Message {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
}

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  tenantId: string;
  coachId?: string;
  createdAt: string;
}

export interface CoachDocumentInfo {
  doc_id: string;
  filename: string;
  client_id: string;
  client_email?: string;
  chunk_count: number;
  uploaded_at?: string;
}

export interface GuardrailsConfig {
  do: string[];
  doNot: string[];
}

export interface IntakeConfig {
  extractionPrompt: string;
}

export interface ReflectionConfig {
  summaryPrompt: string;
}

export interface EscalationConfig {
  message: string;
  keywords: string[];
}

export interface PromptsConfig {
  coachSystemPrompt: string;
  guardrails: GuardrailsConfig;
  intake: IntakeConfig;
  reflection: ReflectionConfig;
  escalation: EscalationConfig;
}
