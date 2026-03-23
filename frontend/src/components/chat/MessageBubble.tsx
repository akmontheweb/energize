import { Message } from '@/types';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const parsedDate = message.createdAt ? new Date(message.createdAt) : null;
  const time =
    parsedDate && !isNaN(parsedDate.getTime())
      ? parsedDate.toLocaleString([], {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      : '';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {!isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center mr-2 mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}
      <div className={`max-w-[75%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
            isUser
              ? 'bg-blue-600 text-white rounded-tr-sm'
              : 'bg-white text-gray-800 border border-gray-200 shadow-sm rounded-tl-sm'
          }`}
        >
          {message.content}
        </div>
        <span className="text-xs text-gray-400 mt-1 px-1">{time}</span>
      </div>
      {isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gray-300 flex items-center justify-center ml-2 mt-1">
          <span className="text-gray-600 text-xs font-bold">You</span>
        </div>
      )}
    </div>
  );
}
