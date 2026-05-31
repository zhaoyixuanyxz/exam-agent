import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { Chat, type ChatBootAction } from "../components/Chat";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { MultiPaperAnalysisPrototype } from "../components/MultiPaperAnalysisPrototype";
import { GovernancePage } from "../pages/GovernancePage";
import { OrgPage } from "../pages/OrgPage";
import { QuestionBankPage } from "../pages/QuestionBankPage";
import { UserGuidePage } from "../pages/UserGuidePage";
import { useStreamJobs } from "../context/StreamJobsContext";

const STORAGE_KEY = "exam-agent-active-cid";
const URL_CID_PARAM = "c";

function readCidFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get(URL_CID_PARAM)?.trim() || null;
  } catch {
    return null;
  }
}

function replaceUrlWithCid(cid: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(URL_CID_PARAM, cid);
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

const navItem = (active: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium ${active ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`;

function NavBar() {
  return (
    <nav className="flex shrink-0 flex-wrap gap-1 border-b border-slate-200/80 bg-white/90 px-2 py-2">
      <NavLink className={({ isActive }) => navItem(isActive)} to="/workbench" end>
        工作台
      </NavLink>
      <NavLink
        className={({ isActive }) =>
          isActive
            ? "rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white"
            : "rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        }
        to="/multi"
      >
        多卷分析
      </NavLink>
      <NavLink className={({ isActive }) => navItem(isActive)} to="/question-bank">
        题库
      </NavLink>
      <NavLink className={({ isActive }) => navItem(isActive)} to="/governance">
        治理
      </NavLink>
      <NavLink className={({ isActive }) => navItem(isActive)} to="/org">
        组织
      </NavLink>
      <NavLink className={({ isActive }) => navItem(isActive)} to="/guide" end>
        操作指南
      </NavLink>
    </nav>
  );
}

export function WorkspaceShell() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);
  const [bootAction, setBootAction] = useState<ChatBootAction | null>(null);
  const { abortJob, generatingIds } = useStreamJobs();
  const loc = useLocation();
  const navigate = useNavigate();

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

  const showSidebar = loc.pathname === "/workbench" || loc.pathname === "/multi";

  return (
    <div className="flex min-h-screen">
      {showSidebar && (
        <ConversationSidebar
          activeId={conversationId}
          refreshKey={listRefreshKey}
          generatingIds={generatingIds}
          onSelect={setConversationId}
          onNewChat={handleNewChat}
          onDeleted={(id) => void handleDeleted(id)}
          onContinueWorkflow={(id) => triggerWorkflowBoot(id, "continue")}
          onRegenerateLast={(id) => triggerWorkflowBoot(id, "regenerate")}
          onOpenMultiPaper={() => void navigate("/multi")}
        />
      )}
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center border-b border-slate-200/80 bg-white/95 px-2 py-1">
          <Link to="/workbench" className="px-1 text-sm font-medium text-slate-700">
            试卷考点 Agent
          </Link>
        </div>
        <NavBar />
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/workbench" replace />} />
            <Route
              path="/workbench"
              element={
                <Chat
                  conversationId={conversationId}
                  bootAction={bootAction}
                  onBootActionConsumed={() => setBootAction(null)}
                  onConversationActivity={bumpSidebar}
                />
              }
            />
            <Route path="/multi" element={<MultiPaperAnalysisPrototype conversationId={conversationId} />} />
            <Route path="/question-bank" element={<QuestionBankPage />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route path="/org" element={<OrgPage />} />
            <Route path="/guide" element={<UserGuidePage />} />
            <Route path="*" element={<Navigate to="/workbench" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
