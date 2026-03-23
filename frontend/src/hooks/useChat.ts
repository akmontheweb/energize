'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Message } from '@/types';
import { WebSocketManager } from '@/lib/websocket';
import { messagesApi } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocketManager | null>(null);
  const assistantMsgIdRef = useRef<string | null>(null);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      setIsLoading(true);
      try {
        const history = await messagesApi.list(sessionId);
        if (!cancelled) setMessages(history);
      } catch {
        // History might not exist yet; start fresh
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, [sessionId]);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocketManager(sessionId, token);
    wsRef.current = ws;

    ws.onMessage((text, done) => {
      if (assistantMsgIdRef.current === null) {
        const newId = `assistant-${Date.now()}`;
        assistantMsgIdRef.current = newId;
        setIsTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            id: newId,
            sessionId,
            role: 'assistant',
            content: text,
            createdAt: new Date().toISOString(),
          },
        ]);
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgIdRef.current
              ? { ...m, content: m.content + text }
              : m
          )
        );
      }

      if (done) {
        assistantMsgIdRef.current = null;
      }
    });

    ws.connect()
      .then(() => setIsConnected(true))
      .catch(() => setIsConnected(false));

    return () => {
      ws.disconnect();
      wsRef.current = null;
      setIsConnected(false);
    };
  }, [sessionId, token]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        sessionId,
        role: 'user',
        content: text,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);
      assistantMsgIdRef.current = null;
      wsRef.current?.send(text);
    },
    [sessionId]
  );

  return { messages, isLoading, isTyping, isConnected, sendMessage };
}
