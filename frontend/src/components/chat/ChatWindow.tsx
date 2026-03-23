'use client';

import { useEffect, useRef } from 'react';
import { useChat } from '@/hooks/useChat';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { Spinner } from '@/components/ui/Spinner';

interface ChatWindowProps {
  sessionId: string;
  readOnly?: boolean;
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center mr-2">
        <span className="text-white text-xs font-bold">AI</span>
      </div>
      <div className="bg-white border border-gray-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex gap-1 items-center h-4">
          <span className="h-2 w-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <span className="h-2 w-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <span className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" />
        </div>
      </div>
    </div>
  );
}

export function ChatWindow({ sessionId, readOnly = false }: ChatWindowProps) {
  const { messages, isLoading, isTyping, isConnected, sendMessage } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Connection status */}
      {!isConnected && (
        <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 text-xs text-yellow-700 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-yellow-400 inline-block" />
          Connecting to session...
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center">
              <div className="h-16 w-16 rounded-full bg-blue-100 flex items-center justify-center mb-4">
                <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-700 mb-1">Start your coaching session</h3>
              <p className="text-sm text-gray-500 max-w-sm">
                Share what&apos;s on your mind. Your AI coach is here to listen and guide you.
              </p>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}
          {isTyping && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </div>

      {readOnly ? (
        <div className="border-t border-gray-200 bg-gray-50 px-4 py-3 text-center text-sm text-gray-400">
          This session is completed. No further messages can be sent.
        </div>
      ) : (
        <ChatInput onSend={sendMessage} disabled={isTyping} />
      )}
    </div>
  );
}
