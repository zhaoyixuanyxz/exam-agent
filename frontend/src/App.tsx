import { useCallback, useEffect, useState } from "react";

import { Chat } from "./components/Chat";
import { ConversationSidebar } from "./components/ConversationSidebar";

const STORAGE_KEY = "exam-agent-active-cid";

export default function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);

  const bumpSidebar = useCallback(() => {
    setListRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const listRes = await fetch("/api/conversations");
        const data = await listRes.json();
        const items = (data.conversations || []) as { id: string }[];
        const stored = localStorage.getItem(STORAGE_KEY);
        if (cancelled) return;
        if (stored && items.some((c) => c.id === stored)) {
          setConversationId(stored);
          return;
        }
        if (items.length > 0) {
          setConversationId(items[0].id);
          return;
        }
        const c = await fetch("/api/conversations", { method: "POST" }).then((r) => r.json());
        if (!cancelled) setConversationId(c.conversation_id as string);
      } catch {
        if (!cancelled) setConversationId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (conversationId) localStorage.setItem(STORAGE_KEY, conversationId);
  }, [conversationId]);

  const handleNewChat = useCallback(async () => {
    const c = await fetch("/api/conversations", { method: "POST" }).then((r) => r.json());
    setConversationId(c.conversation_id as string);
    bumpSidebar();
  }, [bumpSidebar]);

  const handleDeleted = useCallback(
    async (deletedId: string) => {
      if (deletedId !== conversationId) return;
      const listRes = await fetch("/api/conversations");
      const data = await listRes.json();
      const items = (data.conversations || []) as { id: string }[];
      if (items.length > 0) {
        setConversationId(items[0].id);
        return;
      }
      const c = await fetch("/api/conversations", { method: "POST" }).then((r) => r.json());
      setConversationId(c.conversation_id as string);
    },
    [conversationId],
  );

  if (!conversationId) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-600">
        <p className="text-sm">正在加载会话…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <ConversationSidebar
        activeId={conversationId}
        refreshKey={listRefreshKey}
        onSelect={setConversationId}
        onNewChat={handleNewChat}
        onDeleted={(id) => void handleDeleted(id)}
      />
      <main className="min-w-0 flex-1">
        <Chat conversationId={conversationId} onConversationActivity={bumpSidebar} />
      </main>
    </div>
  );
}
