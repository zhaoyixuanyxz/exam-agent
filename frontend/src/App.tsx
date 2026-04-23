import { useCallback, useEffect, useState } from "react";

import { Chat, type ChatBootAction } from "./components/Chat";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { MultiPaperAnalysisPrototype } from "./components/MultiPaperAnalysisPrototype";
import { StreamJobsProvider, useStreamJobs } from "./context/StreamJobsContext";

const STORAGE_KEY = "exam-agent-active-cid";
const URL_CID_PARAM = "c";
const URL_VIEW_PARAM = "view";

function readCidFromUrl(): string | null {
  try {
    const raw = new URLSearchParams(window.location.search).get(URL_CID_PARAM)?.trim();
    if (!raw) return null;
    return raw;
  } catch {
    return null;
  }
}

function replaceUrlWithCid(cid: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(URL_CID_PARAM, cid);
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function readViewFromUrl(): "chat" | "multi" {
  try {
    const v = new URLSearchParams(window.location.search).get(URL_VIEW_PARAM)?.trim();
    return v === "multi" ? "multi" : "chat";
  } catch {
    return "chat";
  }
}

function replaceUrlView(view: "chat" | "multi") {
  const url = new URL(window.location.href);
  if (view === "multi") url.searchParams.set(URL_VIEW_PARAM, "multi");
  else url.searchParams.delete(URL_VIEW_PARAM);
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function AppInner() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mainView, setMainView] = useState<"chat" | "multi">(readViewFromUrl);
  const [listRefreshKey, setListRefreshKey] = useState(0);
  const [bootAction, setBootAction] = useState<ChatBootAction | null>(null);
  const { abortJob, generatingIds } = useStreamJobs();

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
        if (cancelled) return;

        const fromUrl = readCidFromUrl();
        if (fromUrl && items.some((c) => c.id === fromUrl)) {
          setConversationId(fromUrl);
          return;
        }

        const stored = localStorage.getItem(STORAGE_KEY);
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
    if (conversationId) {
      localStorage.setItem(STORAGE_KEY, conversationId);
      replaceUrlWithCid(conversationId);
    }
  }, [conversationId]);

  useEffect(() => {
    replaceUrlView(mainView);
  }, [mainView]);

  const triggerWorkflowBoot = useCallback((id: string, kind: ChatBootAction["kind"]) => {
    setConversationId(id);
    setBootAction({ conversationId: id, kind, token: Date.now() });
  }, []);

  const handleNewChat = useCallback(async () => {
    const c = await fetch("/api/conversations", { method: "POST" }).then((r) => r.json());
    setConversationId(c.conversation_id as string);
    bumpSidebar();
  }, [bumpSidebar]);

  const handleDeleted = useCallback(
    async (deletedId: string) => {
      abortJob(deletedId);
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
    [abortJob, conversationId],
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
        generatingIds={generatingIds}
        onSelect={setConversationId}
        onNewChat={handleNewChat}
        onDeleted={(id) => void handleDeleted(id)}
        onContinueWorkflow={(id) => triggerWorkflowBoot(id, "continue")}
        onRegenerateLast={(id) => triggerWorkflowBoot(id, "regenerate")}
        onOpenMultiPaper={() => setMainView("multi")}
      />
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <nav className="flex shrink-0 flex-wrap gap-2 border-b border-slate-200/80 bg-white/90 px-4 py-2">
          <button
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              mainView === "chat"
                ? "bg-slate-800 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
            onClick={() => setMainView("chat")}
          >
            工作台
          </button>
          <button
            type="button"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              mainView === "multi"
                ? "bg-violet-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
            onClick={() => setMainView("multi")}
          >
            多卷分析（预研）
          </button>
        </nav>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {mainView === "chat" ? (
            <Chat
              conversationId={conversationId}
              bootAction={bootAction}
              onBootActionConsumed={() => setBootAction(null)}
              onConversationActivity={bumpSidebar}
            />
          ) : (
            <MultiPaperAnalysisPrototype conversationId={conversationId} />
          )}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <StreamJobsProvider>
      <AppInner />
    </StreamJobsProvider>
  );
}
