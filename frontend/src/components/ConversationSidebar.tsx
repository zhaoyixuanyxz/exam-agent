import { useCallback, useEffect, useRef, useState } from "react";

const API = "";
const URL_CID_PARAM = "c";

function openConversationInNewTab(id: string) {
  const path = `${window.location.pathname}?${URL_CID_PARAM}=${encodeURIComponent(id)}`;
  window.open(path, "_blank", "noopener,noreferrer");
}

export type ConversationListItem = {
  id: string;
  /** 用户自定义名称；空则列表主文案用 preview */
  title: string | null;
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

function primaryLabel(c: ConversationListItem): string {
  const t = (c.title || "").trim();
  return t || c.preview;
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
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; id: string } | null>(null);
  const [renameDialog, setRenameDialog] = useState<{ id: string; value: string } | null>(null);
  const ctxMenuRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/conversations`);
      const data = await r.json();
      const raw = (data.conversations || []) as Record<string, unknown>[];
      const normalized: ConversationListItem[] = raw.map((row) => ({
        id: String(row.id ?? ""),
        title: row.title != null && row.title !== "" ? String(row.title) : null,
        preview: String(row.preview ?? "（空对话）"),
        last_activity_at: row.last_activity_at != null ? String(row.last_activity_at) : null,
        message_count: Number(row.message_count ?? 0),
        paper_count: Number(row.paper_count ?? 0),
      }));
      setItems(normalized.filter((x) => x.id));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    if (!ctxMenu) return;
    const onDown = (e: MouseEvent) => {
      if (ctxMenuRef.current?.contains(e.target as Node)) return;
      setCtxMenu(null);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [ctxMenu]);

  useEffect(() => {
    if (!ctxMenu && !renameDialog) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setCtxMenu(null);
        setRenameDialog(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ctxMenu, renameDialog]);

  const openRename = useCallback(
    (id: string) => {
      const item = items.find((i) => i.id === id);
      const custom = (item?.title || "").trim();
      const draft = custom || (item?.preview ?? "");
      setRenameDialog({ id, value: draft.slice(0, 512) });
      setCtxMenu(null);
    },
    [items],
  );

  const saveRename = useCallback(async () => {
    if (!renameDialog) return;
    setBusyId(renameDialog.id);
    try {
      const r = await fetch(`${API}/api/conversations/${renameDialog.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: renameDialog.value }),
      });
      if (!r.ok) throw new Error("patch failed");
      setRenameDialog(null);
      await load();
    } catch {
      alert("重命名失败，请稍后重试。");
    } finally {
      setBusyId(null);
    }
  }, [renameDialog, load]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setCtxMenu(null);
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

  const ctxPosition = useCallback((clientX: number, clientY: number) => {
    const pad = 8;
    const w = 160;
    const h = 44;
    let x = clientX;
    let y = clientY;
    if (x + w + pad > window.innerWidth) x = window.innerWidth - w - pad;
    if (y + h + pad > window.innerHeight) y = window.innerHeight - h - pad;
    return { x: Math.max(pad, x), y: Math.max(pad, y) };
  }, []);

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
            <span className="mt-0.5 block">右键会话或点 ✎ 可重命名，便于分类查找。</span>
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
              const customTitle = (c.title || "").trim();
              return (
                <li key={c.id}>
                  <div
                    className={`group flex rounded-xl border transition ${
                      active
                        ? "border-sky-300 bg-softblue/60 shadow-sm"
                        : "border-transparent bg-transparent hover:border-slate-200 hover:bg-mist/80"
                    }`}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      const { x, y } = ctxPosition(e.clientX, e.clientY);
                      setCtxMenu({ x, y, id: c.id });
                    }}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 px-3 py-2.5 text-left text-sm"
                      title="右键可重命名"
                      onClick={() => {
                        onSelect(c.id);
                        setOpen(false);
                      }}
                    >
                      <span className="line-clamp-2 font-medium text-slate-800">
                        {primaryLabel(c)}
                      </span>
                      {customTitle && (
                        <span className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">
                          {c.preview}
                        </span>
                      )}
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
                      className="shrink-0 px-1 text-slate-400 opacity-75 transition hover:text-sky-600 hover:opacity-100 md:opacity-60 md:group-hover:opacity-100"
                      title="重命名"
                      aria-label="重命名对话"
                      disabled={busyId === c.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        openRename(c.id);
                      }}
                    >
                      ✎
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

      {ctxMenu && (
        <div
          ref={ctxMenuRef}
          role="menu"
          className="fixed z-[45] min-w-[140px] rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg"
          style={{ left: ctxMenu.x, top: ctxMenu.y }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-slate-700 hover:bg-sky-50"
            onClick={() => openRename(ctxMenu.id)}
          >
            重命名…
          </button>
        </div>
      )}

      {renameDialog && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 p-4"
          onMouseDown={() => setRenameDialog(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-4 shadow-xl"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h2 className="mb-3 text-sm font-semibold text-slate-800">重命名对话</h2>
            <p className="mb-2 text-xs text-slate-500">
              留空并保存将恢复为默认预览（首条用户消息摘要）。
            </p>
            <input
              type="text"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 outline-none ring-sky-300 focus:border-sky-300 focus:ring-2"
              value={renameDialog.value}
              maxLength={512}
              autoFocus
              placeholder="输入名称"
              onChange={(e) =>
                setRenameDialog({ ...renameDialog, value: e.target.value.slice(0, 512) })
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveRename();
              }}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
                onClick={() => setRenameDialog(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
                disabled={busyId === renameDialog.id}
                onClick={() => void saveRename()}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
