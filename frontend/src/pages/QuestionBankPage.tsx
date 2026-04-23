import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../api/client";

type Row = {
  id: string;
  stem: string;
  qtype: string;
  subject_label?: string | null;
  grade_label?: string | null;
  quality_status?: string;
  source_paper_name?: string | null;
  created_at?: string | null;
};

type ListResp = { items: Row[]; total: number; page: number; page_size: number };

export function QuestionBankPage() {
  const [q, setQ] = useState("");
  const [data, setData] = useState<ListResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sel, setSel] = useState<Row | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await apiGet<ListResp>("/api/question-bank", { q: q || undefined, page: 1, page_size: 50, sort: "created_desc" });
      setData(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-slate-600">
          关键词
          <input
            className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void load()}
            placeholder="题干包含…"
          />
        </label>
        <button type="button" className="rounded bg-slate-800 px-3 py-1 text-sm text-white" onClick={() => void load()}>
          检索
        </button>
        {loading && <span className="text-xs text-slate-500">加载中</span>}
        {err && <span className="text-xs text-red-600">{err}</span>}
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-hidden md:grid-cols-2">
        <div className="min-h-0 overflow-auto rounded border border-slate-200 bg-white">
          <table className="w-full min-w-full text-left text-sm">
            <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs text-slate-600">
              <tr>
                <th className="p-2">题型</th>
                <th className="p-2">学科</th>
                <th className="p-2">题干摘要</th>
                <th className="p-2">质量</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((r) => (
                <tr
                  key={r.id}
                  className={`cursor-pointer border-b border-slate-100 hover:bg-slate-50 ${
                    sel?.id === r.id ? "bg-violet-50" : ""
                  }`}
                  onClick={() => setSel(r)}
                >
                  <td className="p-2 text-slate-800">{r.qtype || "—"}</td>
                  <td className="p-2 text-slate-600">{r.subject_label || "—"}</td>
                  <td className="p-2 text-slate-800 line-clamp-2" title={r.stem}>
                    {r.stem || "—"}
                  </td>
                  <td className="p-2 text-slate-500">{r.quality_status || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && (
            <p className="border-t border-slate-200 p-2 text-xs text-slate-500">共 {data.total} 条</p>
          )}
        </div>
        <div className="min-h-0 overflow-auto rounded border border-slate-200 bg-white p-3 text-sm text-slate-800">
          {sel ? (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">id: {sel.id}</p>
              <p className="whitespace-pre-wrap">{sel.stem}</p>
              <p>
                来源：{sel.source_paper_name || "—"} · 创建 {sel.created_at || "—"}
              </p>
              <p>
                <Link className="text-violet-600 underline" to="/governance">
                  去治理台纠错
                </Link>
              </p>
            </div>
          ) : (
            <p className="text-slate-500">请从左侧选择题目</p>
          )}
        </div>
      </div>
    </div>
  );
}
