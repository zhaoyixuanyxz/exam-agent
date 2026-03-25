import { useCallback, useEffect, useRef, useState } from "react";

import { displayUserMessageContent, textForChatDisplay } from "../utils/chatDisplay";

type Artifact = {
  kind: string;
  name: string;
  path: string;
  url?: string;
  knowledge_point_key?: string | null;
};

type Bubble = { role: "user" | "assistant"; text: string };

const API = "";

type ChatProps = {
  conversationId: string;
  /** 发送一轮完成后用于刷新侧边栏排序与预览 */
  onConversationActivity?: () => void;
};

export function Chat({ conversationId, onConversationActivity }: ChatProps) {
  const [input, setInput] = useState("");
  const [sourceType, setSourceType] = useState("pdf");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [streaming, setStreaming] = useState("");
  const [statusHint, setStatusHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [bubbles, streaming, statusHint]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mRes, aRes] = await Promise.all([
          fetch(`${API}/api/conversations/${conversationId}/messages`),
          fetch(`${API}/api/conversations/${conversationId}/artifacts`),
        ]);
        if (cancelled) return;
        if (!mRes.ok) {
          setBubbles([]);
          setArtifacts([]);
          return;
        }
        const mj = await mRes.json();
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
        setStreaming("");
        setStatusHint("");
        if (aRes.ok) {
          const aj = await aRes.json();
          setArtifacts((aj.items || []) as Artifact[]);
        } else {
          setArtifacts([]);
        }
      } catch {
        if (!cancelled) {
          setBubbles([]);
          setArtifacts([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  const send = useCallback(async () => {
    if (busy) return;
    const cid = conversationId;
    const fd = new FormData();
    fd.append("conversation_id", cid);
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
    setBusy(true);
    setStreaming("");
    setStatusHint("");

    try {
      const res = await fetch(`${API}/api/chat/stream`, { method: "POST", body: fd });
      const reader = res.body?.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let assistant = "";
      if (!reader) throw new Error("无响应流");
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const block of parts) {
          const line = block.startsWith("data: ") ? block.slice(6) : block;
          if (!line.trim()) continue;
          let ev: { event?: string; data?: Record<string, unknown> };
          try {
            ev = JSON.parse(line);
          } catch {
            continue;
          }
          if (ev.event === "status" && ev.data?.message) {
            setStatusHint(String(ev.data.message));
          }
          if (ev.event === "token" && ev.data?.t) {
            setStatusHint("");
            assistant += String(ev.data.t);
            setStreaming(textForChatDisplay(assistant));
          }
          if (ev.event === "artifacts" && ev.data?.items) {
            setArtifacts(ev.data.items as Artifact[]);
          }
          if (ev.event === "error" && ev.data?.message) {
            assistant += `\n⚠️ ${ev.data.message}`;
            setStreaming(textForChatDisplay(assistant));
          }
        }
      }
      if (assistant) {
        setBubbles((b) => [
          ...b,
          { role: "assistant", text: textForChatDisplay(assistant) },
        ]);
      }
      setStreaming("");
      setStatusHint("");
      onConversationActivity?.();
    } catch (e) {
      setBubbles((b) => [
        ...b,
        { role: "assistant", text: `请求失败：${e instanceof Error ? e.message : e}` },
      ]);
      setStreaming("");
      setStatusHint("");
    } finally {
      setBusy(false);
    }
  }, [busy, conversationId, file, input, onConversationActivity, sourceType, url]);

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
          带水印）。左侧可管理历史会话与恢复误关页面。
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

      {artifacts.length > 0 && (
        <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50/80 p-3 text-sm text-amber-950">
          <div className="mb-2 flex items-center gap-2 font-medium">
            <span>📎</span> 生成文件
          </div>
          <ul className="flex flex-col gap-1">
            {artifacts.map((a, i) => (
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
