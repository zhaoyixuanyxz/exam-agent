import { useCallback, useEffect, useRef, useState } from "react";

import { useStreamJobs, type StreamArtifact } from "../context/StreamJobsContext";
import { displayUserMessageContent, textForChatDisplay } from "../utils/chatDisplay";

type Bubble = { role: "user" | "assistant"; text: string };

const API = "";

type ChatProps = {
  conversationId: string;
  /** 发送一轮完成后用于刷新侧边栏排序与预览 */
  onConversationActivity?: () => void;
};

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
  const bottomRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef(conversationId);

  conversationIdRef.current = conversationId;

  const busy = job.busy;
  const streaming = job.streaming;
  const statusHint = job.statusHint;
  const displayArtifacts =
    job.busy && job.artifacts.length > 0 ? job.artifacts : artifacts;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [bubbles, streaming, statusHint]);

  useEffect(() => {
    const err = job.streamError;
    if (!err) return;
    setBubbles((b) => [...b, { role: "assistant", text: err }]);
    clearStreamError(conversationId);
  }, [job.streamError, conversationId, clearStreamError]);

  useEffect(() => {
    const cid = conversationId;
    let cancelled = false;
    (async () => {
      try {
        const [mRes, aRes] = await Promise.all([
          fetch(`${API}/api/conversations/${cid}/messages`),
          fetch(`${API}/api/conversations/${cid}/artifacts`),
        ]);
        if (cancelled || conversationIdRef.current !== cid) return;
        if (!mRes.ok) {
          setBubbles([]);
          setArtifacts([]);
          return;
        }
        const mj = await mRes.json();
        if (cancelled || conversationIdRef.current !== cid) return;
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
          if (cancelled || conversationIdRef.current !== cid) return;
          setArtifacts((aj.items || []) as StreamArtifact[]);
        } else {
          setArtifacts([]);
        }
      } catch {
        if (!cancelled && conversationIdRef.current === cid) {
          setBubbles([]);
          setArtifacts([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, streamRefreshNonce]);

  const send = useCallback(async () => {
    if (busy) return;
    const requestCid = conversationId;
    const fd = new FormData();
    fd.append("conversation_id", requestCid);
    fd.append("message", input);
    fd.append("source_type", sourceType);
    if (url.trim()) fd.append("url", url.trim());
    if (file) fd.append("file", file);

    const userLine =
      input.trim() ||
      (file ? `📎 上传：${file.name}` : url.trim() ? `🔗 ${url}` : "请开始分析");
    setBubbles((b) => [...b, { role: "user", text: userLine }]);
    setInput("");
    setFile(null);

    startStream(requestCid, fd, {
      onComplete: () => {
        onConversationActivity?.();
      },
    });
  }, [busy, conversationId, file, input, onConversationActivity, sourceType, startStream, url]);

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
          上传 PDF / Word、粘贴 URL 或正文，助手会帮你对齐年级科目、拆解考点并生成分块练习 PDF（楷体 · 米白底 ·
          带水印）。切换左侧其他会话时，当前生成可在后台继续；列表中带「生成中」标记。
        </p>
      </header>

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
              type="file"
              className="hidden"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        {file && <p className="text-xs text-slate-500">已选：{file.name}</p>}
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
