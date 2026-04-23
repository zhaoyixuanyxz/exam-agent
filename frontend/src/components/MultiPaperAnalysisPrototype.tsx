import { useCallback, useEffect, useState } from "react";

const API = "";

type PaperListItem = {
  id: string;
  display_name: string | null;
  structured_confirm_status?: string;
};

type AnalysisResponse = {
  conversation_id: string;
  paper_summaries: Array<{
    paper_id: string;
    display_name: string | null;
    structured_title: string;
    structured_version: number;
    question_count: number;
    knowledge_point_count: number;
  }>;
  knowledge_coverage_diff: {
    per_paper: Array<{
      paper_id: string;
      display_name: string | null;
      knowledge_point_keys: string[];
      unique_vs_others: string[];
    }>;
    common_across_selected: string[];
  };
  question_type_distribution: Array<{
    paper_id: string;
    display_name: string | null;
    counts: Array<{ qtype: string; count: number }>;
  }>;
  repeated_knowledge_points: Array<{
    knowledge_point_key: string;
    name: string;
    paper_count: number;
    total_question_hits: number;
  }>;
  chapter_distribution: Array<{
    paper_id: string;
    display_name: string | null;
    chapters: Array<{ hint: string; count: number }>;
  }>;
  notes: string[];
};

export function MultiPaperAnalysisPrototype(props: { conversationId: string }) {
  const { conversationId } = props;
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loadingList, setLoadingList] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [useCanonical, setUseCanonical] = useState(true);

  const loadPapers = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/conversations/${conversationId}/papers`);
      if (!r.ok) throw new Error(`加载材料失败 ${r.status}`);
      const data = await r.json();
      const list = (data.papers || []) as PaperListItem[];
      setPapers(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingList(false);
    }
  }, [conversationId]);

  useEffect(() => {
    void loadPapers();
  }, [loadPapers]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const runAnalysis = async () => {
    const ids = [...selected];
    if (ids.length < 2) {
      setError("请至少选择 2 份材料");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/conversations/${conversationId}/multi-paper-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: ids, use_canonical_knowledge_points: useCanonical }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || `分析失败 ${r.status}`);
      }
      setResult((await r.json()) as AnalysisResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <div className="rounded-2xl border border-white/60 bg-white/80 p-4 shadow-sm backdrop-blur">
        <h2 className="text-base font-semibold text-slate-800">多卷 / 教研分析</h2>
        <p className="mt-1 text-sm text-slate-600">
          基于题目资产与考点映射做确定性聚合。支持标准考点主数据口径（V2.3），见下方「使用标准考点」选项。
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium text-slate-800">选择材料（≥2）</span>
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:bg-slate-100"
            onClick={() => void loadPapers()}
            disabled={loadingList}
          >
            刷新列表
          </button>
        </div>
        {loadingList ? (
          <p className="text-sm text-slate-500">加载中…</p>
        ) : papers.length === 0 ? (
          <p className="text-sm text-slate-500">本会话暂无材料</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {papers.map((p) => (
              <li key={p.id}>
                <label className="flex cursor-pointer items-start gap-2 rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2 text-sm hover:bg-sky-50/60">
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => toggle(p.id)}
                    className="mt-1"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium text-slate-800">
                      {p.display_name?.trim() || `材料 ${p.id.slice(0, 8)}…`}
                    </span>
                    <span className="ml-2 text-xs text-slate-500">
                      结构化：{p.structured_confirm_status || "—"}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={useCanonical}
            onChange={(e) => setUseCanonical(e.target.checked)}
          />
          使用标准考点主数据口径（V2.3 归并后统计）
        </label>
        <button
          type="button"
          disabled={running || selected.size < 2}
          className="mt-3 rounded-xl bg-gradient-to-r from-violet-500 to-indigo-500 px-4 py-2 text-sm font-medium text-white shadow disabled:opacity-50"
          onClick={() => void runAnalysis()}
        >
          {running ? "分析中…" : "运行多卷聚合分析"}
        </button>
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
      </div>

      {result ? (
        <div className="flex flex-col gap-4 pb-8">
          {result.notes?.length ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-3 text-sm text-amber-900">
              <p className="font-medium">提示</p>
              <ul className="mt-1 list-inside list-disc">
                {result.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">材料摘要</h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {result.paper_summaries.map((s) => (
                <div key={s.paper_id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs">
                  <div className="font-medium text-slate-800">
                    {s.display_name || s.paper_id.slice(0, 8) + "…"}
                  </div>
                  <div className="mt-1 text-slate-600">
                    标题：{s.structured_title || "—"} · 版本 v{s.structured_version} · 题量 {s.question_count} ·
                    考点数 {s.knowledge_point_count}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">考点覆盖与差异</h3>
            <p className="mt-1 text-xs text-slate-500">
              共有考点（所选卷交集）：{result.knowledge_coverage_diff.common_across_selected.join(", ") || "—"}
            </p>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {result.knowledge_coverage_diff.per_paper.map((slice) => (
                <div key={slice.paper_id} className="rounded-xl border border-violet-100 bg-violet-50/40 p-3 text-xs">
                  <div className="font-medium text-violet-900">
                    {slice.display_name || slice.paper_id.slice(0, 8) + "…"}
                  </div>
                  <div className="mt-2 max-h-40 overflow-y-auto text-slate-700">
                    <span className="text-slate-500">独有考点：</span>
                    {slice.unique_vs_others.length ? slice.unique_vs_others.join(", ") : "—"}
                  </div>
                  <div className="mt-2 max-h-32 overflow-y-auto text-slate-600">
                    <span className="text-slate-500">全部考点 key：</span>
                    {slice.knowledge_point_keys.join(", ") || "—"}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">题型分布</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {result.question_type_distribution.map((d) => (
                <div key={d.paper_id} className="rounded-xl border border-sky-100 bg-sky-50/50 p-3 text-xs">
                  <div className="font-medium text-sky-900">
                    {d.display_name || d.paper_id.slice(0, 8) + "…"}
                  </div>
                  <ul className="mt-2 space-y-1 text-slate-700">
                    {d.counts.map((c) => (
                      <li key={c.qtype}>
                        {c.qtype}：{c.count}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">重复考点（至少两卷出现）</h3>
            <ul className="mt-2 space-y-1 text-xs text-slate-700">
              {result.repeated_knowledge_points.length ? (
                result.repeated_knowledge_points.map((r) => (
                  <li key={r.knowledge_point_key}>
                    <span className="font-mono text-slate-800">{r.knowledge_point_key}</span>
                    {r.name ? `（${r.name}）` : ""} — {r.paper_count} 卷 / 题目命中 {r.total_question_hits}
                  </li>
                ))
              ) : (
                <li>暂无（需考点分析映射且多卷共享同一 key）</li>
              )}
            </ul>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-800">章节提示分布（book_chapter_hint）</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {result.chapter_distribution.map((d) => (
                <div key={d.paper_id} className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3 text-xs">
                  <div className="font-medium text-emerald-900">
                    {d.display_name || d.paper_id.slice(0, 8) + "…"}
                  </div>
                  {d.chapters.length ? (
                    <ul className="mt-2 space-y-1 text-slate-700">
                      {d.chapters.map((c) => (
                        <li key={c.hint}>
                          {c.hint}：{c.count}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-slate-500">暂无考点章节提示</p>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
