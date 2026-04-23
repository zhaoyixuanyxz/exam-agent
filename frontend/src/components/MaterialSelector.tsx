import { useCallback, useState } from "react";

const API = "";

export type PaperListItem = {
  id: string;
  source_type: string;
  raw_path: string | null;
  display_name?: string | null;
  structured_confirm_status?: string;
  /** 服务端保存的练习生成配置快照 */
  last_practice_config?: Record<string, unknown> | null;
};

type Props = {
  conversationId: string;
  papers: PaperListItem[];
  targetPaperId: string | null;
  onTargetChange: (id: string) => void;
  onPapersChanged: () => void;
};

function shortId(id: string) {
  return id.length >= 8 ? id.slice(0, 8) : id;
}

function displayLabel(p: PaperListItem) {
  if (p.display_name && p.display_name.trim()) return p.display_name.trim();
  if (p.raw_path) {
    const base = p.raw_path.split("/").pop() || p.raw_path;
    if (base.length > 32) return base.slice(0, 29) + "…";
    return base;
  }
  return `材料·${shortId(p.id)}`;
}

export function MaterialSelector({
  conversationId,
  papers,
  targetPaperId,
  onTargetChange,
  onPapersChanged,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const current = papers.find((x) => x.id === targetPaperId) || null;

  const startEdit = useCallback(() => {
    if (!current) return;
    setNameDraft(current.display_name?.trim() || displayLabel(current));
    setEditing(true);
    setNote(null);
  }, [current]);

  const saveName = useCallback(async () => {
    if (!current) return;
    const v = nameDraft.trim();
    if (!v) {
      setNote("名称不能为空");
      return;
    }
    setSaveBusy(true);
    setNote(null);
    try {
      const r = await fetch(`${API}/api/conversations/${conversationId}/papers/${current.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: v }),
      });
      if (!r.ok) {
        setNote("重命名失败");
        return;
      }
      setEditing(false);
      onPapersChanged();
    } catch {
      setNote("网络错误");
    } finally {
      setSaveBusy(false);
    }
  }, [conversationId, current, nameDraft, onPapersChanged]);

  if (papers.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-600">暂无材料，请上传或粘贴文本创建试卷。</div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-sm">
      <div className="mb-2 text-sm font-semibold text-slate-800">当前目标材料</div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <label className="flex flex-1 items-center gap-2 text-sm text-slate-700">
          <span className="shrink-0 text-slate-500">选择</span>
          <select
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5"
            value={targetPaperId ?? ""}
            onChange={(e) => onTargetChange(e.target.value)}
          >
            {papers.map((p) => (
              <option key={p.id} value={p.id}>
                {displayLabel(p)} ({shortId(p.id)}…)
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          {!editing ? (
            <button
              type="button"
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-50"
              onClick={startEdit}
            >
              重命名
            </button>
          ) : (
            <>
              <input
                className="min-w-[160px] flex-1 rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
              />
              <button
                type="button"
                disabled={saveBusy}
                className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                onClick={() => void saveName()}
              >
                保存
              </button>
              <button
                type="button"
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
                onClick={() => setEditing(false)}
              >
                取消
              </button>
            </>
          )}
        </div>
      </div>
      {current && (
        <p className="mt-2 text-xs text-slate-500">
          结构确认状态：<span className="font-mono">{current.structured_confirm_status ?? "—"}</span>
        </p>
      )}
      {note && <p className="mt-2 text-sm text-rose-700">{note}</p>}
    </div>
  );
}
