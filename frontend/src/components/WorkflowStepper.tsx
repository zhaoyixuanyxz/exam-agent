import { useEffect, useMemo, useState } from "react";

import { useStreamJobs } from "../context/StreamJobsContext";

const API = "";

export type WorkflowStep = { key: string; name: string; state: string };

type Props = {
  conversationId: string;
  paperId: string | null;
  refreshKey: number;
  busy: boolean;
  clientErrorHint: string | null;
  onClearClientErrorHint: () => void;
  onRetryUpload: () => void;
  onRetryStructure: () => void;
  onRetryAnalyze: () => void;
  onRetryGenerate: () => void;
  onRetryDownload: () => void;
};

const stateLabel: Record<string, string> = {
  not_started: "未开始",
  in_progress: "进行中",
  pending_confirm: "待确认",
  completed: "已完成",
  failed: "失败",
};

function badgeClass(state: string) {
  switch (state) {
    case "completed":
      return "border-emerald-200 bg-emerald-50 text-emerald-900";
    case "in_progress":
      return "border-sky-200 bg-sky-50 text-sky-900";
    case "pending_confirm":
      return "border-amber-200 bg-amber-50 text-amber-950";
    case "failed":
      return "border-rose-200 bg-rose-50 text-rose-900";
    default:
      return "border-slate-200 bg-white text-slate-600";
  }
}

function inferFailedStepFromClientText(text: string | null | undefined): string | null {
  if (!text?.trim()) return null;
  const s = text;
  if (!/失败|错误|处理出错|请求失败|Error/i.test(s)) return null;
  const low = s.toLowerCase();
  if ((/文件超过|413|解析失败|上传/.test(s) && /失败|出错|错/.test(s)) || /413/.test(s)) return "upload";
  if (/拆题|structure_exam|拆题失败|结构化.*失败/.test(s) || (low.includes("structure") && /失败|错/.test(s)))
    return "structure";
  if (/先确认.*结构化|请先在「结构化结果」/.test(s)) return "structure";
  if (/考点|knowledge|分析失败|考点分析/.test(s) || (low.includes("knowledge") && /失败|错/.test(s)))
    return "analyze";
  if (/出题|练习.*失败|练习卷|generate_chunk|render/.test(s) || (low.includes("pdf") && /失败|错/.test(s)))
    return "generate";
  if (/仅网络|请检查网络|fetch failed/i.test(s)) return null;
  return "structure";
}

type WorkflowResponse = {
  steps?: WorkflowStep[];
  last_failed_step?: string | null;
  agent_run_active?: boolean;
};

export function WorkflowStepper({
  conversationId,
  paperId,
  refreshKey,
  busy,
  clientErrorHint,
  onClearClientErrorHint,
  onRetryUpload,
  onRetryStructure,
  onRetryAnalyze,
  onRetryGenerate,
  onRetryDownload,
}: Props) {
  const { getJob } = useStreamJobs();
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [serverFailedStep, setServerFailedStep] = useState<string | null>(null);
  const [agentActive, setAgentActive] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const job = getJob(conversationId);
  const liveStreamError = job.streamError;

  useEffect(() => {
    if (!paperId) {
      setSteps([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [w, a] = await Promise.all([
          fetch(`${API}/api/conversations/${conversationId}/workflow?paper_id=${encodeURIComponent(paperId)}`),
          fetch(`${API}/api/conversations/${conversationId}/agent-run-active`),
        ]);
        if (cancelled) return;
        if (!w.ok) {
          setErr("无法加载流程状态");
          setSteps([]);
          return;
        }
        const j = (await w.json()) as WorkflowResponse;
        setSteps((j.steps || []) as WorkflowStep[]);
        setServerFailedStep((j.last_failed_step as string | null) ?? null);
        if (a.ok) {
          const aj = (await a.json()) as { active?: boolean };
          setAgentActive(!!aj.active);
        } else {
          setAgentActive(!!j.agent_run_active);
        }
        setErr(null);
      } catch {
        if (!cancelled) setErr("网络错误");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, paperId, refreshKey]);

  const effectiveFailedKey = useMemo(() => {
    const fromStep = steps.find((s) => s.state === "failed")?.key;
    if (fromStep) return fromStep;
    if (serverFailedStep) return serverFailedStep;
    const t = clientErrorHint || liveStreamError;
    return inferFailedStepFromClientText(t);
  }, [steps, serverFailedStep, clientErrorHint, liveStreamError]);

  const byKey = (k: string) => steps.find((s) => s.key === k);

  if (!paperId) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-3 text-sm text-slate-500">
        请先上传材料并选择目标试卷，以显示主流程步骤。
      </div>
    );
  }

  if (err) {
    return <div className="rounded-xl border border-rose-100 bg-rose-50 p-2 text-sm text-rose-900">{err}</div>;
  }

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-3 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-slate-800">主流程</div>
        {agentActive && (
          <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800">助手处理中</span>
        )}
      </div>
      {(clientErrorHint || liveStreamError) && (
        <div className="mb-2 flex flex-col gap-1 rounded-lg border border-amber-200 bg-amber-50/90 px-2 py-1.5 text-xs text-amber-950">
          <span>若上一轮未成功，可点对应步骤的「重试」。</span>
          <span className="text-amber-900/80">{clientErrorHint || liveStreamError}</span>
          <button
            type="button"
            className="self-start text-[11px] text-sky-800 underline"
            onClick={onClearClientErrorHint}
          >
            不再提示
          </button>
        </div>
      )}
      <ol className="flex flex-col gap-2">
        {steps.map((s) => {
          const fail = s.state === "failed" || effectiveFailedKey === s.key;
          const highlight = fail && s.state !== "completed";
          return (
            <li
              key={s.key}
              className={`flex flex-col gap-1.5 rounded-xl border px-2.5 py-2 text-xs ${badgeClass(s.state)}${
                highlight ? " ring-2 ring-rose-300 ring-offset-1" : ""
              }`}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="font-medium text-slate-800">{s.name}</span>
                <span className="ml-auto shrink-0 text-[11px] opacity-90">
                  {stateLabel[s.state] ?? s.state}
                </span>
              </div>
              {renderRetryRow(s, {
                busy,
                agentActive,
                byKey,
                fail,
                onRetryUpload,
                onRetryStructure,
                onRetryAnalyze,
                onRetryGenerate,
                onRetryDownload,
              })}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

type RowCtx = {
  busy: boolean;
  agentActive: boolean;
  byKey: (k: string) => WorkflowStep | undefined;
  fail: boolean;
  onRetryUpload: () => void;
  onRetryStructure: () => void;
  onRetryAnalyze: () => void;
  onRetryGenerate: () => void;
  onRetryDownload: () => void;
};

function renderRetryRow(s: WorkflowStep, ctx: RowCtx) {
  const { busy, agentActive, byKey, fail, onRetryUpload, onRetryStructure, onRetryAnalyze, onRetryGenerate, onRetryDownload } = ctx;
  const canClick = !busy;
  const danger = (label: string, on: () => void) => (
    <button
      type="button"
      disabled={!canClick}
      onClick={on}
      className="self-start rounded-md border border-rose-200/90 bg-white px-2 py-0.5 text-[11px] text-rose-900 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {label}
    </button>
  );
  const normal = (label: string, on: () => void) => (
    <button
      type="button"
      disabled={!canClick}
      onClick={on}
      className="self-start rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {label}
    </button>
  );

  if (s.state === "completed" && s.key !== "download") {
    return null;
  }
  if (s.state === "in_progress" && agentActive) {
    return <span className="text-[10px] text-slate-500">助手中，请稍候；若长时间卡住可刷新页面后再试下方「重试」。</span>;
  }

  switch (s.key) {
    case "upload": {
      if (s.state === "completed") return null;
      return fail ? danger("重试：去上传", onRetryUpload) : normal("去上传", onRetryUpload);
    }
    case "structure": {
      if (s.state === "completed") return null;
      if (fail) return danger("重试拆题", onRetryStructure);
      if (s.state === "pending_confirm") return normal("重新拆题", onRetryStructure);
      return normal(s.state === "not_started" ? "开始拆题" : "继续拆题", onRetryStructure);
    }
    case "analyze": {
      const st = byKey("structure");
      if (st && st.state !== "completed") return <span className="text-[10px] text-slate-500">需先完成并确认「结构化」。</span>;
      if (s.state === "completed") return null;
      if (fail) return danger("重试考点分析", onRetryAnalyze);
      return normal("继续 / 重试 考点分析", onRetryAnalyze);
    }
    case "generate": {
      const a = byKey("analyze");
      if (a && a.state !== "completed") return <span className="text-[10px] text-slate-500">需先完成「分析考点」。</span>;
      if (s.state === "completed") return null;
      if (fail) return danger("重试生成练习", onRetryGenerate);
      return normal("继续 / 重试 生成练习", onRetryGenerate);
    }
    case "download": {
      const g = byKey("generate");
      if (g && g.state !== "completed") {
        return <span className="text-[10px] text-slate-500">需先完成「生成练习」后，方可在下方下载产物。</span>;
      }
      if (fail) return danger("重试：刷新产物", onRetryDownload);
      if (s.state === "completed") return normal("刷新产物列表", onRetryDownload);
      return normal("刷新下方产物", onRetryDownload);
    }
    default:
      return null;
  }
}
