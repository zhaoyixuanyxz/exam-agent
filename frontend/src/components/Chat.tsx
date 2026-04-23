import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useStreamJobs, type StreamArtifact } from "../context/StreamJobsContext";
import { displayUserMessageContent, textForChatDisplay } from "../utils/chatDisplay";
import { MaterialSelector, type PaperListItem } from "./MaterialSelector";
import { StructuredResultPanel } from "./StructuredResultPanel";
import { WorkflowStepper } from "./WorkflowStepper";

type Bubble = { role: "user" | "assistant"; text: string };

const API = "";

type ChatProps = {
  conversationId: string;
  /** 发送一轮完成后用于刷新侧边栏排序与预览 */
  onConversationActivity?: () => void;
};

function parsePageRanges(s: string): number[][] | null {
  const parts = s
    .split(/[,，]/)
    .map((x) => x.trim())
    .filter(Boolean);
  const out: number[][] = [];
  for (const p of parts) {
    const m = p.match(/^(\d+)\s*[-–~～]\s*(\d+)$/);
    if (!m) return null;
    const a = parseInt(m[1], 10);
    const b = parseInt(m[2], 10);
    if (a < 1 || b < 1 || a > b) return null;
    out.push([a, b]);
  }
  return out.length ? out : null;
}

export function Chat({ conversationId, onConversationActivity }: ChatProps) {
  const { getJob, startStream, clearStreamError } = useStreamJobs();
  const job = getJob(conversationId);
  const streamRefreshNonce = job.refreshNonce;

  const [input, setInput] = useState("");
  const [sourceType, setSourceType] = useState("pdf");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [artifacts, setArtifacts] = useState<StreamArtifact[]>([]);
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [targetPaperId, setTargetPaperId] = useState<string | null>(null);
  const [v2Tick, setV2Tick] = useState(0);
  const [clientStreamErrorHint, setClientStreamErrorHint] = useState<string | null>(null);
  const [splitRanges, setSplitRanges] = useState("");
  const [splitBusy, setSplitBusy] = useState(false);
  const [splitNote, setSplitNote] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const conversationIdRef = useRef(conversationId);

  conversationIdRef.current = conversationId;

  const busy = job.busy;
  const streaming = job.streaming;
  const statusHint = job.statusHint;
  const displayArtifacts =
    job.busy && job.artifacts.length > 0 ? job.artifacts : artifacts;

  const loadPapers = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/conversations/${conversationId}/papers`);
      if (!r.ok) return;
      const j = await r.json();
      setPapers(j.papers || []);
    } catch {
      setPapers([]);
    }
  }, [conversationId]);

  useEffect(() => {
    void loadPapers();
  }, [conversationId, streamRefreshNonce, loadPapers]);

  useEffect(() => {
    setTargetPaperId(null);
    setV2Tick(0);
    setClientStreamErrorHint(null);
  }, [conversationId]);

  useEffect(() => {
    if (papers.length === 0) return;
    setTargetPaperId((cur) => {
      if (cur && papers.some((p) => p.id === cur)) return cur;
      return papers[0].id;
    });
  }, [papers]);

  useEffect(() => {
    if (job.streamPaperId) {
      setTargetPaperId(job.streamPaperId);
    }
  }, [job.streamPaperId]);

  const splitTarget = useMemo(() => {
    const pdf = papers.filter((x) => x.source_type === "pdf" && x.raw_path);
    if (!pdf.length) return null;
    if (targetPaperId) {
      const byTarget = pdf.find((x) => x.id === targetPaperId);
      if (byTarget) return byTarget;
    }
    const sid = job.streamPaperId;
    if (sid) {
      const hit = pdf.find((x) => x.id === sid);
      if (hit) return hit;
    }
    return pdf[0] ?? null;
  }, [papers, job.streamPaperId, targetPaperId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [bubbles, streaming, statusHint]);

  useEffect(() => {
    const err = job.streamError;
    if (!err) return;
    setClientStreamErrorHint(err);
    setBubbles((b) => [...b, { role: "assistant", text: err }]);
    clearStreamError(conversationId);
  }, [job.streamError, conversationId, clearStreamError]);

  const loadThread = useCallback(async (cid: string, isStale?: () => boolean) => {
    const stale = isStale ?? (() => conversationIdRef.current !== cid);
    try {
      const [mRes, aRes] = await Promise.all([
        fetch(`${API}/api/conversations/${cid}/messages`),
        fetch(`${API}/api/conversations/${cid}/artifacts`),
      ]);
      if (stale()) return;
      if (!mRes.ok) {
        setBubbles([]);
        setArtifacts([]);
        return;
      }
      const mj = await mRes.json();
      if (stale()) return;
      const next: Bubble[] = [];
      for (const msg of mj.messages || []) {
        if (msg.role === "user") {
          next.push({
            role: "user",
            text: displayUserMessageContent(String(msg.content || "")),
          });
        } else if (msg.role === "assistant") {
          next.push({
            role: "assistant",
            text: textForChatDisplay(String(msg.content || "")),
          });
        }
      }
      setBubbles(next);
      if (aRes.ok) {
        const aj = await aRes.json();
        if (stale()) return;
        setArtifacts((aj.items || []) as StreamArtifact[]);
      } else {
        setArtifacts([]);
      }
    } catch {
      if (!stale() && conversationIdRef.current === cid) {
        setBubbles([]);
        setArtifacts([]);
      }
    }
  }, []);

  useEffect(() => {
    const cid = conversationId;
    let cancelled = false;
    const stale = () => cancelled || conversationIdRef.current !== cid;
    void loadThread(cid, stale);
    return () => {
      cancelled = true;
    };
  }, [conversationId, streamRefreshNonce, loadThread]);

  /** 刷新后 SSE 已断但服务端仍在生成时，轮询消息与附件直至后台任务结束。 */
  useEffect(() => {
    const cid = conversationId;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | undefined;
    const stale = () => cancelled || conversationIdRef.current !== cid;

    void (async () => {
      try {
        const st = await fetch(`${API}/api/conversations/${cid}/agent-run-active`);
        if (!st.ok || stale()) return;
        const j = (await st.json()) as { active?: boolean };
        if (!j.active) return;
        await loadThread(cid, stale);
        interval = setInterval(() => {
          void (async () => {
            try {
              const st2 = await fetch(`${API}/api/conversations/${cid}/agent-run-active`);
              if (!st2.ok || stale()) return;
              const j2 = (await st2.json()) as { active?: boolean };
              if (stale()) return;
              if (j2.active) {
                await loadThread(cid, stale);
              } else {
                if (interval) clearInterval(interval);
                interval = undefined;
                await loadThread(cid, stale);
                onConversationActivity?.();
              }
            } catch {
              /* ignore */
            }
          })();
        }, 2200);
      } catch {
        /* ignore */
      }
    })();

    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [conversationId, loadThread, onConversationActivity]);

  const handleRestructure = useCallback(() => {
    if (busy || !targetPaperId) return;
    setClientStreamErrorHint(null);
    const fd = new FormData();
    fd.append("conversation_id", conversationId);
    fd.append("message", "请仅对当前目标试卷调用 structure_exam_paper 工具完成拆题，不要跳过。");
    fd.append("source_type", "text");
    fd.append("target_paper_id", targetPaperId);
    setBubbles((b) => [...b, { role: "user", text: "（重新结构化：请运行拆题）" }]);
    startStream(conversationId, fd, {
      onComplete: () => {
        onConversationActivity?.();
        void loadPapers();
        setV2Tick((t) => t + 1);
        setClientStreamErrorHint(null);
      },
    });
  }, [busy, conversationId, loadPapers, onConversationActivity, startStream, targetPaperId]);

  const handleRetryAnalyze = useCallback(() => {
    if (busy || !targetPaperId) return;
    setClientStreamErrorHint(null);
    const fd = new FormData();
    fd.append("conversation_id", conversationId);
    fd.append(
      "message",
      "请对当前目标材料：若尚未完成 save_alignment_metadata，请先向用户确认并保存年级、科目与题型数量；在结构化结果已确认的前提下，调用 run_knowledge_analysis 完成考点分析。",
    );
    fd.append("source_type", "text");
    fd.append("target_paper_id", targetPaperId);
    setBubbles((b) => [...b, { role: "user", text: "（主流程重试：考点分析）" }]);
    startStream(conversationId, fd, {
      onComplete: () => {
        onConversationActivity?.();
        void loadPapers();
        setV2Tick((t) => t + 1);
        setClientStreamErrorHint(null);
      },
    });
  }, [busy, conversationId, loadPapers, onConversationActivity, startStream, targetPaperId]);

  const handleRetryGenerate = useCallback(() => {
    if (busy || !targetPaperId) return;
    setClientStreamErrorHint(null);
    const fd = new FormData();
    fd.append("conversation_id", conversationId);
    fd.append(
      "message",
      "请基于当前已完成的考点分析，为主要考点调用 generate_chunk_practice_pdfs_batch 或 generate_chunk_practice_pdf 生成分块练习 PDF 与答案（按考点批量、避免遗漏）。",
    );
    fd.append("source_type", "text");
    fd.append("target_paper_id", targetPaperId);
    setBubbles((b) => [...b, { role: "user", text: "（主流程重试：生成练习）" }]);
    startStream(conversationId, fd, {
      onComplete: () => {
        onConversationActivity?.();
        void loadPapers();
        setV2Tick((t) => t + 1);
        setClientStreamErrorHint(null);
      },
    });
  }, [busy, conversationId, loadPapers, onConversationActivity, startStream, targetPaperId]);

  const handleRetryDownload = useCallback(() => {
    setClientStreamErrorHint(null);
    void loadThread(conversationId);
    setV2Tick((t) => t + 1);
  }, [conversationId, loadThread]);

  const handleRetryUpload = useCallback(() => {
    setClientStreamErrorHint(null);
    fileInputRef.current?.click();
  }, []);

  const send = useCallback(async () => {
    if (busy) return;
    setClientStreamErrorHint(null);
    const requestCid = conversationId;
    const fd = new FormData();
    fd.append("conversation_id", requestCid);
    fd.append("message", input);
    fd.append("source_type", sourceType);
    if (url.trim()) fd.append("url", url.trim());
    if (file) fd.append("file", file);
    if (targetPaperId) fd.append("target_paper_id", targetPaperId);

    const userLine =
      input.trim() ||
      (file ? `📎 上传：${file.name}` : url.trim() ? `🔗 ${url}` : "请开始分析");
    setBubbles((b) => [...b, { role: "user", text: userLine }]);
    setInput("");
    setFile(null);

    startStream(requestCid, fd, {
      onComplete: () => {
        onConversationActivity?.();
        void loadPapers();
        setV2Tick((t) => t + 1);
        setClientStreamErrorHint(null);
      },
    });
  }, [busy, conversationId, file, input, loadPapers, onConversationActivity, sourceType, startStream, targetPaperId, url]);

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-6 md:pl-2">
      <header className="mb-4 flex flex-col gap-2 rounded-2xl border border-white/60 bg-white/70 p-4 shadow-sm backdrop-blur">
        <div className="flex flex-wrap items-center gap-2 text-slate-700">
          <span className="text-2xl" aria-hidden>
            📚
          </span>
          <h1 className="text-lg font-semibold tracking-tight">试卷考点拆解助手</h1>
          <span className="rounded-full bg-softmint/80 px-2 py-0.5 text-xs text-emerald-800">
            ✨ 多轮对话
          </span>
        </div>
        <p className="text-sm text-slate-500">
          上传 PDF / Word、粘贴 URL 或正文；请在下方选择目标材料、确认结构化结果后再继续对齐与考点分析。切换左侧其他会话时，当前生成可在后台继续；列表中带「生成中」标记。
        </p>
      </header>

      <div className="mb-3 flex flex-col gap-3">
        <WorkflowStepper
          conversationId={conversationId}
          paperId={targetPaperId}
          refreshKey={v2Tick}
          busy={busy}
          clientErrorHint={clientStreamErrorHint}
          onClearClientErrorHint={() => setClientStreamErrorHint(null)}
          onRetryUpload={handleRetryUpload}
          onRetryStructure={handleRestructure}
          onRetryAnalyze={handleRetryAnalyze}
          onRetryGenerate={handleRetryGenerate}
          onRetryDownload={handleRetryDownload}
        />
        <MaterialSelector
          conversationId={conversationId}
          papers={papers}
          targetPaperId={targetPaperId}
          onTargetChange={setTargetPaperId}
          onPapersChanged={() => {
            void loadPapers();
            setV2Tick((t) => t + 1);
          }}
        />
        <StructuredResultPanel
          conversationId={conversationId}
          paperId={targetPaperId}
          refreshKey={v2Tick}
          onAfterSave={() => setV2Tick((t) => t + 1)}
          onRestructure={handleRestructure}
          busy={busy}
        />
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border border-slate-200/80 bg-paper/90 p-4 shadow-inner">
        {bubbles.length === 0 && !streaming && !statusHint && (
          <div className="rounded-xl border border-dashed border-sky-200 bg-softblue/40 p-6 text-center text-slate-600">
            <p className="mb-2 text-3xl">🎯</p>
            <p className="text-sm">
              你好！我是朱老师的试卷小助手 🌿 试试上传一份试卷，或者说一下年级和科目～
            </p>
          </div>
        )}
        {bubbles.map((m, i) => (
          <div
            key={i}
            className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
              m.role === "user"
                ? "ml-auto bg-gradient-to-br from-sky-100 to-indigo-50 text-slate-800"
                : "mr-auto border border-slate-100 bg-white text-slate-800"
            }`}
          >
            {m.role === "assistant" && (
              <span className="mr-1 text-base" aria-hidden>
                🤖
              </span>
            )}
            <span className="whitespace-pre-wrap">{m.text}</span>
          </div>
        ))}
        {(statusHint || streaming) && (
          <div className="mr-auto max-w-[92%] rounded-2xl border border-violet-100 bg-softlilac/50 px-4 py-3 text-sm text-slate-800">
            {statusHint && (
              <p className="mb-2 text-xs text-violet-700/90">{statusHint}</p>
            )}
            {streaming && (
              <>
                <span className="mr-1" aria-hidden>
                  ✍️
                </span>
                <span className="whitespace-pre-wrap">{streaming}</span>
              </>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {displayArtifacts.length > 0 && (
        <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50/80 p-3 text-sm text-amber-950">
          <div className="mb-2 flex items-center gap-2 font-medium">
            <span>📎</span> 生成文件
          </div>
          <ul className="flex flex-col gap-1">
            {displayArtifacts.map((a, i) => (
              <li key={i}>
                {a.url ? (
                  <a
                    className="text-sky-700 underline decoration-sky-300 hover:text-sky-900"
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {a.kind === "markdown" ? "📄" : "📕"} {a.name}
                  </a>
                ) : (
                  <span>
                    {a.name} <span className="text-slate-400">(路径未映射 URL)</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {splitTarget && (
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/90 p-3 text-xs text-slate-600">
          <div className="font-medium text-slate-800">
            按页拆分 PDF（目标材料 id：{splitTarget.id.slice(0, 8)}…）
          </div>
          <p className="mt-1">
            用逗号分隔多个区间，如 <span className="rounded bg-white px-1 font-mono">1-3, 5-7</span>
            （从 1 起算，闭区间）。拆分后生成新材料；后续对话默认仍绑定当前轮次的 paper_id，请在消息里说明要用的材料 id。
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              className="min-w-[180px] flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1 font-mono"
              placeholder="例：1-4, 5-10"
              value={splitRanges}
              onChange={(e) => setSplitRanges(e.target.value)}
              disabled={splitBusy}
            />
            <button
              type="button"
              disabled={splitBusy}
              className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1 text-sky-900 hover:bg-sky-100 disabled:opacity-50"
              onClick={() => void (async () => {
                setSplitNote(null);
                const ranges = parsePageRanges(splitRanges);
                if (!ranges) {
                  setSplitNote("页码格式不对，请使用 起始-结束，多个用逗号分隔。");
                  return;
                }
                setSplitBusy(true);
                try {
                  const res = await fetch(
                    `${API}/api/exam-papers/${splitTarget.id}/split-by-pages`,
                    {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        conversation_id: conversationId,
                        ranges,
                      }),
                    },
                  );
                  const j = await res.json().catch(() => ({}));
                  if (!res.ok) {
                    const d = j.detail as unknown;
                    const msg =
                      typeof d === "string"
                        ? d
                        : Array.isArray(d)
                          ? d
                              .map((x: { msg?: string }) =>
                                typeof x === "object" && x && "msg" in x
                                  ? String((x as { msg?: string }).msg)
                                  : JSON.stringify(x),
                              )
                              .join("; ")
                          : "拆分失败";
                    setSplitNote(msg);
                    return;
                  }
                  const ids = (j.new_papers || []) as { id: string; label?: string }[];
                  const idLine = ids.map((x) => `${x.label ?? "新材料"}: ${x.id.slice(0, 8)}…`).join("；");
                  setSplitNote(
                    `${j.message || "拆分完成。"} 新材料：${idLine || "（见响应）"}`,
                  );
                  setSplitRanges("");
                  await loadPapers();
                  onConversationActivity?.();
                } catch {
                  setSplitNote("网络错误，请重试。");
                } finally {
                  setSplitBusy(false);
                }
              })()}
            >
              {splitBusy ? "拆分中…" : "拆分"}
            </button>
          </div>
          {splitNote && <p className="mt-2 whitespace-pre-wrap text-emerald-900">{splitNote}</p>}
        </div>
      )}

      <div className="mt-4 space-y-2 rounded-2xl border border-white/60 bg-white/80 p-3 shadow-md backdrop-blur">
        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
          <label className="flex items-center gap-1">
            <span>🗂️</span>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2 py-1"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
            >
              <option value="pdf">PDF</option>
              <option value="docx">Word</option>
              <option value="url">URL</option>
              <option value="text">粘贴文本</option>
            </select>
          </label>
          <label className="flex flex-1 min-w-[200px] items-center gap-1">
            <span>🔗</span>
            <input
              className="w-full rounded-lg border border-slate-200 px-2 py-1"
              placeholder="网页链接（选 URL 时）"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label className="flex cursor-pointer items-center gap-1 rounded-lg border border-dashed border-slate-300 bg-mist px-2 py-1 hover:bg-slate-50">
            <span>📎</span>
            <span>选择文件</span>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        {file && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>已选：{file.name}</span>
            <button
              type="button"
              className="rounded-md border border-slate-300 bg-white px-2 py-0.5 text-slate-600 hover:bg-slate-50"
              onClick={() => {
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            >
              清除
            </button>
          </div>
        )}
        <div className="flex gap-2">
          <textarea
            className="min-h-[72px] flex-1 resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-sky-300 focus:outline-none focus:ring-1 focus:ring-sky-200"
            placeholder="说点什么… 例如：这是初三数学月考，请结构化并问我题型数量 🌸"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => void send()}
            className="self-end rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 px-5 py-2 text-sm font-medium text-white shadow-md transition hover:opacity-95 disabled:opacity-50"
          >
            {busy ? "⏳" : "发送 🚀"}
          </button>
        </div>
      </div>
    </div>
  );
}
