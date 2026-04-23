import { useMemo } from "react";

import type { StreamArtifact } from "../context/StreamJobsContext";

const CATEGORY_ORDER = [
  "knowledge_markdown",
  "practice_question_pdf",
  "practice_answer_pdf",
  "other",
] as const;

const CATEGORY_LABEL: Record<string, string> = {
  knowledge_markdown: "考点说明",
  practice_question_pdf: "练习卷",
  practice_answer_pdf: "参考答案",
  other: "其他",
};

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

type Props = {
  items: StreamArtifact[];
  busy: boolean;
  onRegenerateFromArtifact: (art: StreamArtifact) => void;
};

export function ArtifactCenter({ items, busy, onRegenerateFromArtifact }: Props) {
  const grouped = useMemo(() => {
    const m = new Map<string, StreamArtifact[]>();
    for (const c of CATEGORY_ORDER) m.set(c, []);
    for (const a of items) {
      const cat = a.category && m.has(a.category) ? a.category : "other";
      m.get(cat)!.push(a);
    }
    return CATEGORY_ORDER.map((c) => ({ category: c, list: m.get(c)! })).filter((g) => g.list.length > 0);
  }, [items]);

  if (items.length === 0) return null;

  return (
    <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50/80 p-3 text-sm text-amber-950">
      <div className="mb-2 flex items-center gap-2 font-medium">
        <span aria-hidden>📦</span>
        产物中心
      </div>
      <div className="flex flex-col gap-3">
        {grouped.map(({ category, list }) => (
          <div key={category}>
            <div className="mb-1 text-xs font-semibold text-amber-900/90">
              {CATEGORY_LABEL[category] ?? category}
            </div>
            <ul className="flex flex-col gap-2">
              {list.map((a) => {
                const canRegen =
                  !!a.knowledge_point_key &&
                  (a.kind === "pdf_question" || a.kind === "pdf_answer");
                return (
                  <li
                    key={`${a.id ?? a.path}-${a.kind}`}
                    className="rounded-lg border border-amber-100/80 bg-white/70 px-2 py-2 text-xs"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {a.url ? (
                          <a
                            className="font-medium text-sky-800 underline decoration-sky-300 hover:text-sky-950"
                            href={a.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {a.kind === "markdown" ? "📄 " : "📕 "}
                            {a.name}
                          </a>
                        ) : (
                          <span className="font-medium">
                            {a.name}{" "}
                            <span className="font-normal text-slate-400">(无下载链接)</span>
                          </span>
                        )}
                        <div className="mt-1 space-y-0.5 text-[11px] text-slate-600">
                          {a.created_at && (
                            <div>
                              <span className="text-slate-400">时间：</span>
                              {formatTime(a.created_at)}
                            </div>
                          )}
                          {a.paper_display_name && (
                            <div>
                              <span className="text-slate-400">材料：</span>
                              {a.paper_display_name}
                            </div>
                          )}
                          {a.source_tool && (
                            <div>
                              <span className="text-slate-400">来源：</span>
                              {a.source_tool}
                            </div>
                          )}
                          {a.output_mode && (
                            <div>
                              <span className="text-slate-400">输出：</span>
                              {a.output_mode === "questions_only" ? "仅题目" : "题目+答案"}
                            </div>
                          )}
                          {a.config_snapshot && typeof a.config_snapshot.question_count === "number" && (
                            <div>
                              <span className="text-slate-400">题量：</span>
                              {a.config_snapshot.question_count}
                            </div>
                          )}
                        </div>
                      </div>
                      {canRegen && (
                        <button
                          type="button"
                          disabled={busy}
                          className="shrink-0 rounded-lg border border-violet-200 bg-violet-50 px-2 py-1 text-[11px] font-medium text-violet-900 hover:bg-violet-100 disabled:opacity-50"
                          onClick={() => onRegenerateFromArtifact(a)}
                        >
                          按此考点再生成
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
