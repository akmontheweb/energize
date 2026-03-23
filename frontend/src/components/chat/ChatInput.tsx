'use client';

import { useState, useRef, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/Button';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-3">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            rows={1}
            placeholder="Type your message… (Enter to send, Shift+Enter for newline)"
            disabled={disabled}
            className="w-full resize-none rounded-xl border border-gray-300 bg-gray-50 px-4 py-2.5
              text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2
              focus:ring-blue-500 focus:border-transparent disabled:opacity-50 max-h-40 overflow-y-auto"
          />
        </div>
        <Button
          onClick={handleSend}
          disabled={!text.trim() || disabled}
          className="flex-shrink-0 h-10 w-10 !p-0 rounded-xl"
          aria-label="Send message"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </Button>
      </div>
    </div>
  );
}
