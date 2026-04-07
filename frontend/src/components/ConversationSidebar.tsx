import { useCallback, useEffect, useState } from "react";

const API = "";
const URL_CID_PARAM = "c";

function openConversationInNewTab(id: string) {
  const path = `${window.location.pathname}?${URL_CID_PARAM}=${encodeURIComponent(id)}`;
  window.open(path, "_blank", "noopener,noreferrer");
}

export type ConversationListItem = {
  id: string;
  preview: string;
  last_activity_at: string | null;
  message_count: number;
  paper_count: number;
};

type Props = {
  activeId: string;
  refreshKey: number;
  /** 后台流式生成中的会话 id（可与当前选中不同） */
  generatingIds?: string[];
  onSelect: (id: string) => void;
  onNewChat: () => Promise<void>;
  /** 删除成功后调用；若删掉的是当前会话，由父组件切换 activeId。 */
  onDeleted?: (id: string) => void | Promise<void>;
};

function formatShortDate(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    if (sameDay) {
      return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function ConversationSidebar({
  activeId,
  refreshKey,
  generatingIds = [],
  onSelect,
  onNewChat,
  onDeleted,
}: Props) {
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/conversations`);
      const data = await r.json();
      setItems((data.conversations || []) as ConversationListItem[]);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("确定删除该对话？关联上传文件与生成产物将从服务器移除，且不可恢复。")) {
      return;
    }
    setBusyId(id);
    try {
      const r = await fetch(`${API}/api/conversations/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error("删除失败");
      if (onDeleted) await onDeleted(id);
      await load();
    } catch {
      alert("删除失败，请稍后重试。");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <button
        type="button"
        className="fixed left-3 top-3 z-40 flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white/90 text-lg shadow-md backdrop-blur md:hidden"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? "收起对话列表" : "展开对话列表"}
      >
        {open ? "◀" : "☰"}
      </button>
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[min(100%,280px)] flex-col border-r border-slate-200/80 bg-white/85 shadow-lg backdrop-blur transition-transform duration-200 md:static md:z-0 md:w-72 md:translate-x-0 md:shadow-none ${
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex flex-col gap-2 border-b border-slate-100 p-3 pt-14 md:pt-3">
          <button
            type="button"
            className="rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 px-3 py-2.5 text-sm font-medium text-white shadow-md transition hover:opacity-95"
            onClick={() => void onNewChat()}
          >
            ＋ 新对话
          </button>
          <p className="text-xs leading-snug text-slate-500">
            切换会话时当前生成可在后台继续（列表显示「生成中」）。↗ 可在新标签页并行打开会话。
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {loading && <p className="px-2 py-4 text-center text-xs text-slate-400">加载列表…</p>}
          {!loading && items.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-slate-400">暂无历史，点「新对话」开始</p>
          )}
          <ul className="flex flex-col gap-1">
            {items.map((c) => {
              const active = c.id === activeId;
              const generating = generatingIds.includes(c.id);
              return (
                <li key={c.id}>
                  <div
                    className={`group flex rounded-xl border transition ${
                      active
                        ? "border-sky-300 bg-softblue/60 shadow-sm"
                        : "border-transparent bg-transparent hover:border-slate-200 hover:bg-mist/80"
                    }`}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 px-3 py-2.5 text-left text-sm"
                      onClick={() => {
                        onSelect(c.id);
                        setOpen(false);
                      }}
                    >
                      <span className="line-clamp-2 text-slate-800">{c.preview}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-slate-400">
                        <span>{formatShortDate(c.last_activity_at)}</span>
                        {generating && (
                          <span className="font-medium text-violet-600">生成中</span>
                        )}
                        {c.message_count > 0 && <span>{c.message_count} 条消息</span>}
                        {c.paper_count > 0 && <span>{c.paper_count} 份材料</span>}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="shrink-0 px-1.5 text-slate-400 opacity-70 transition hover:text-sky-600 hover:opacity-100"
                      title="新标签页打开此会话（可并行生成）"
                      aria-label="新标签页打开此会话"
                      onClick={(e) => {
                        e.stopPropagation();
                        openConversationInNewTab(c.id);
                      }}
                    >
                      ↗
                    </button>
                    <button
                      type="button"
                      disabled={busyId === c.id}
                      className="shrink-0 px-2 text-slate-400 opacity-60 transition hover:text-rose-600 hover:opacity-100 disabled:opacity-30"
                      title="删除对话"
                      aria-label="删除对话"
                      onClick={(e) => void handleDelete(e, c.id)}
                    >
                      🗑
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-slate-900/20 md:hidden"
          aria-label="关闭侧边栏"
          onClick={() => setOpen(false)}
        />
      )}
    </>
  );
}
