import { useCallback, useEffect, useState } from "react";

const API = "";

type Summary = {
  title: string;
  section_count: number;
  question_count: number;
  qtype_counts: Record<string, number>;
} | null;

type StructuredPayload = {
  paper_id: string;
  display_name: string | null;
  structured_confirm_status: string;
  structured_version: number;
  parsed_json: Record<string, unknown> | null;
  summary: Summary;
  anomalies: string[];
  alignment_json: Record<string, unknown> | null;
};

type Props = {
  conversationId: string;
  paperId: string | null;
  refreshKey: number;
  onAfterSave: () => void;
  onRestructure: () => void;
  busy: boolean;
};

export function StructuredResultPanel({
  conversationId,
  paperId,
  refreshKey,
  onAfterSave,
  onRestructure,
  busy,
}: Props) {
  const [data, setData] = useState<StructuredPayload | null>(null);
  const [draft, setDraft] = useState("");
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    if (!paperId) {
      setData(null);
      setDraft("");
      return;
    }
    setLoadErr(null);
    try {
      const r = await fetch(
        `${API}/api/conversations/${conversationId}/papers/${paperId}/structured`,
      );
      if (!r.ok) {
        setLoadErr("无法加载结构化结果");
        setData(null);
        return;
      }
      const j = (await r.json()) as StructuredPayload;
      setData(j);
      setDraft(JSON.stringify(j.parsed_json ?? {}, null, 2));
    } catch {
      setLoadErr("网络错误");
    }
  }, [conversationId, paperId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const save = useCallback(async () => {
    if (!paperId) return;
    setSaving(true);
    setSaveErr(null);
    try {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(draft) as Record<string, unknown>;
      } catch (e) {
        setSaveErr("JSON 格式不正确");
        setSaving(false);
        return;
      }
      const r = await fetch(
        `${API}/api/conversations/${conversationId}/papers/${paperId}/structured`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ parsed_json: parsed }),
        },
      );
      if (!r.ok) {
        const t = await r.text();
        setSaveErr(t || "保存失败");
        return;
      }
      await load();
      onAfterSave();
    } catch {
      setSaveErr("网络错误");
    } finally {
      setSaving(false);
    }
  }, [conversationId, paperId, draft, load, onAfterSave]);

  const confirm = useCallback(async () => {
    if (!paperId) return;
    setConfirming(true);
    setSaveErr(null);
    try {
      const r = await fetch(
        `${API}/api/conversations/${conversationId}/papers/${paperId}/structured/confirm`,
        { method: "POST" },
      );
      if (!r.ok) {
        const t = await r.text();
        setSaveErr(t || "确认失败");
        return;
      }
      await load();
      onAfterSave();
    } catch {
      setSaveErr("网络错误");
    } finally {
      setConfirming(false);
    }
  }, [conversationId, paperId, load, onAfterSave]);

  if (!paperId) {
    return null;
  }

  if (loadErr) {
    return (
      <div className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-sm text-rose-900">
        {loadErr}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-slate-800">结构化结果</div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-sm text-violet-900 disabled:opacity-50"
            onClick={onRestructure}
          >
            重新结构化
          </button>
        </div>
      </div>

      {data?.summary && (
        <div className="mb-2 grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50/80 p-2 text-sm sm:grid-cols-2">
          <div>
            <span className="text-slate-500">标题</span>{" "}
            <span className="font-medium text-slate-900">{data.summary.title || "（无）"}</span>
          </div>
          <div>
            <span className="text-slate-500">大题 / 小题</span>{" "}
            <span className="font-mono text-slate-900">
              {data.summary.section_count} / {data.summary.question_count}
            </span>
          </div>
          <div className="sm:col-span-2">
            <span className="text-slate-500">题型分布</span>{" "}
            <span className="text-slate-800">
              {Object.keys(data.summary.qtype_counts || {}).length
                ? Object.entries(data.summary.qtype_counts || {})
                    .map(([k, v]) => `${k}×${v}`)
                    .join("，")
                : "—"}
            </span>
          </div>
        </div>
      )}

      {data?.alignment_json && (
        <p className="mb-2 text-xs text-slate-600">
          已保存年级科目：
          <span className="font-mono text-slate-800">
            {String((data.alignment_json as { grade_min?: string }).grade_min ?? "")}—
            {String((data.alignment_json as { grade_max?: string }).grade_max ?? "")}{" "}
            {(data.alignment_json as { subject?: string }).subject ?? ""}
          </span>
        </p>
      )}

      {data && data.anomalies && data.anomalies.length > 0 && (
        <ul className="mb-2 list-inside list-disc rounded-xl border border-amber-200 bg-amber-50/90 p-2 text-sm text-amber-950">
          {data.anomalies.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}

      <p className="mb-1 text-xs text-slate-500">
        状态：{" "}
        <span className="font-mono text-slate-800">{data?.structured_confirm_status ?? "—"}</span>{" "}
        · 版本 {data?.structured_version ?? 0}
      </p>

      <label className="mb-1 block text-xs text-slate-500">structured JSON（高级编辑）</label>
      <textarea
        className="mb-2 min-h-[180px] w-full rounded-xl border border-slate-200 bg-white px-2 py-2 font-mono text-xs text-slate-900"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        spellCheck={false}
      />

      {saveErr && <p className="mb-2 text-sm text-rose-700">{saveErr}</p>}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={saving}
          onClick={() => void save()}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {saving ? "保存中…" : "保存修改"}
        </button>
        <button
          type="button"
          disabled={confirming || (data?.structured_confirm_status === "confirmed")}
          onClick={() => void confirm()}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {data?.structured_confirm_status === "confirmed" ? "已确认" : confirming ? "确认中…" : "确认结构化结果"}
        </button>
      </div>
    </div>
  );
}
