import { useCallback } from "react";

export type PracticeGenerateConfig = {
  question_count: number;
  difficulty: "easy" | "medium" | "hard";
  question_types: string[];
  output_mode: "questions_only" | "questions_and_answers";
  paper_mode: "single" | "AB";
  use_original_figures: boolean;
  include_figures: boolean;
};

export const defaultPracticeConfig: PracticeGenerateConfig = {
  question_count: 10,
  difficulty: "medium",
  question_types: [],
  output_mode: "questions_and_answers",
  paper_mode: "single",
  use_original_figures: false,
  include_figures: true,
};

const QTYPE_OPTIONS = ["单选", "多选", "填空", "简答", "判断"] as const;

export function practiceConfigToJson(cfg: PracticeGenerateConfig): string {
  const o: Record<string, unknown> = {
    question_count: cfg.question_count,
    difficulty: cfg.difficulty,
    output_mode: cfg.output_mode,
    use_original_figures: cfg.use_original_figures,
    include_figures: cfg.include_figures,
  };
  if (cfg.question_types.length > 0) {
    o.question_types = cfg.question_types;
  }
  if (cfg.paper_mode !== "single") {
    o.paper_mode = cfg.paper_mode;
  }
  return JSON.stringify(o);
}

export function mergeServerPracticeConfig(
  raw: Record<string, unknown> | null | undefined,
): PracticeGenerateConfig {
  const base = { ...defaultPracticeConfig };
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return base;
  if (typeof raw.question_count === "number" && raw.question_count >= 1) {
    base.question_count = Math.min(60, Math.floor(raw.question_count));
  }
  const d = String(raw.difficulty || "").toLowerCase();
  if (d === "easy" || d === "medium" || d === "hard") {
    base.difficulty = d;
  }
  const om = String(raw.output_mode || "");
  if (om === "questions_only" || om === "questions_and_answers") {
    base.output_mode = om;
  }
  const pm = String(raw.paper_mode || "");
  if (pm === "AB" || pm === "single") {
    base.paper_mode = pm;
  }
  if (typeof raw.use_original_figures === "boolean") {
    base.use_original_figures = raw.use_original_figures;
  }
  if (typeof raw.include_figures === "boolean") {
    base.include_figures = raw.include_figures;
  }
  if (Array.isArray(raw.question_types)) {
    const set = new Set<string>();
    for (const x of raw.question_types) {
      const s = String(x).trim();
      if ((QTYPE_OPTIONS as readonly string[]).includes(s)) set.add(s);
    }
    base.question_types = Array.from(set);
  }
  return base;
}

type Props = {
  value: PracticeGenerateConfig;
  onChange: (next: PracticeGenerateConfig) => void;
  disabled?: boolean;
};

export function PracticeGenerateConfigPanel({ value, onChange, disabled }: Props) {
  const patch = useCallback(
    (partial: Partial<PracticeGenerateConfig>) => {
      onChange({ ...value, ...partial });
    },
    [onChange, value],
  );

  const toggleQtype = useCallback(
    (q: string) => {
      const set = new Set(value.question_types);
      if (set.has(q)) set.delete(q);
      else set.add(q);
      patch({ question_types: Array.from(set) });
    },
    [patch, value.question_types],
  );

  return (
    <div className="rounded-xl border border-violet-100 bg-softlilac/40 p-3 text-xs text-slate-700 shadow-sm">
      <div className="mb-2 flex items-center gap-2 font-medium text-slate-800">
        <span aria-hidden>⚙️</span>
        练习生成配置
        <span className="font-normal text-slate-500">（随消息提交，服务端与材料绑定）</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-slate-500">题量</span>
          <input
            type="number"
            min={1}
            max={60}
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 font-mono text-sm"
            disabled={disabled}
            value={value.question_count}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              patch({ question_count: Number.isFinite(n) ? Math.min(60, Math.max(1, n)) : 10 });
            }}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-slate-500">难度</span>
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
            disabled={disabled}
            value={value.difficulty}
            onChange={(e) =>
              patch({ difficulty: e.target.value as PracticeGenerateConfig["difficulty"] })
            }
          >
            <option value="easy">较易</option>
            <option value="medium">中等</option>
            <option value="hard">较难</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5 sm:col-span-2">
          <span className="text-[11px] text-slate-500">输出形式</span>
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
            disabled={disabled}
            value={value.output_mode}
            onChange={(e) =>
              patch({ output_mode: e.target.value as PracticeGenerateConfig["output_mode"] })
            }
          >
            <option value="questions_and_answers">题目 + 参考答案（PDF）</option>
            <option value="questions_only">仅题目（PDF）</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-slate-500">试卷模式（预留）</span>
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm"
            disabled={disabled}
            value={value.paper_mode}
            onChange={(e) =>
              patch({ paper_mode: e.target.value as PracticeGenerateConfig["paper_mode"] })
            }
          >
            <option value="single">单卷</option>
            <option value="AB">A/B 卷</option>
          </select>
        </label>
      </div>
      <div className="mt-2">
        <span className="text-[11px] text-slate-500">题型（不选表示不限制）</span>
        <div className="mt-1 flex flex-wrap gap-2">
          {QTYPE_OPTIONS.map((q) => (
            <label
              key={q}
              className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-0.5"
            >
              <input
                type="checkbox"
                disabled={disabled}
                checked={value.question_types.includes(q)}
                onChange={() => toggleQtype(q)}
              />
              {q}
            </label>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-4">
        <label className="inline-flex items-center gap-1.5">
          <input
            type="checkbox"
            disabled={disabled}
            checked={value.include_figures}
            onChange={(e) => patch({ include_figures: e.target.checked })}
          />
          允许配图
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input
            type="checkbox"
            disabled={disabled}
            checked={value.use_original_figures}
            onChange={(e) => patch({ use_original_figures: e.target.checked })}
          />
          尝试嵌入原卷附图
        </label>
      </div>
    </div>
  );
}
