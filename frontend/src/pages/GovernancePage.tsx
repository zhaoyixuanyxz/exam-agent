import { useCallback, useEffect, useState } from "react";

import { apiGet, DEFAULT_USER } from "../api/client";

type Row = { id: string; stem: string; quality_status?: string; qtype: string };

type ListResp = { items: Row[]; total: number };

export function GovernancePage() {
  const [items, setItems] = useState<Row[]>([]);
  const [qid, setQid] = useState<string | null>(null);
  const [review, setReview] = useState("approved");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await apiGet<ListResp>("/api/question-bank", { quality: "pending", page: 1, page_size: 30, sort: "created_desc" });
    setItems(r.items || []);
  }, []);

  useEffect(() => {
    void load().catch(() => {
      // ignore
    });
  }, [load]);

  const save = () => {
    if (!qid) {
      setMsg("请先选择题目");
      return;
    }
    setMsg(null);
    void (async () => {
      try {
        const r = await fetch(`/api/question-bank/${qid}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": localStorage.getItem("exam-agent-user-id") || DEFAULT_USER,
          },
          body: JSON.stringify({ review_status: review }),
        });
        if (!r.ok) throw new Error(await r.text());
        setMsg("已保存");
        await load();
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "失败");
      }
    })();
  };

  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3 text-sm text-slate-800">
      <h2 className="text-base font-semibold">题目治理</h2>
      <p className="text-slate-600">选择题目并更新审核状态（质量= pending 的列表）。</p>
      {items.length === 0 && <p className="text-slate-500">暂无待处理题目；若无资产请先在工作台完成结构化确认。</p>}
      <div className="flex flex-col gap-2">
        {items.map((r) => (
          <div key={r.id} className="rounded border border-slate-200 p-2">
            <label className="flex cursor-pointer gap-2">
              <input type="radio" name="qi" checked={qid === r.id} onChange={() => setQid(r.id)} />
              <span className="line-clamp-2">{r.stem}</span>
            </label>
            <p className="pl-6 text-xs text-slate-500">质量 {r.quality_status || "—"}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select className="rounded border border-slate-200 px-2 py-1" value={review} onChange={(e) => setReview(e.target.value)}>
          <option value="pending_review">待审核</option>
          <option value="approved">已审核</option>
          <option value="corrected">已修正</option>
          <option value="deprecated">已废弃</option>
        </select>
        <button type="button" className="rounded bg-slate-800 px-3 py-1 text-white" onClick={save}>
          保存审核状态
        </button>
        {msg && <span className="text-xs text-slate-600">{msg}</span>}
      </div>
    </div>
  );
}
