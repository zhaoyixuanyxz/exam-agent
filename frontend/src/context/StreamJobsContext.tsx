import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { textForChatDisplay } from "../utils/chatDisplay";

const API = "";

export type StreamArtifact = {
  kind: string;
  name: string;
  path: string;
  url?: string;
  knowledge_point_key?: string | null;
};

type JobSnapshot = {
  busy: boolean;
  streaming: string;
  statusHint: string;
  artifacts: StreamArtifact[];
  refreshNonce: number;
  streamError: string | null;
  /** 最近一次流式轮次 meta 中的 paper_id（用于按页拆分等） */
  streamPaperId: string | null;
};

function emptyJob(): JobSnapshot {
  return {
    busy: false,
    streaming: "",
    statusHint: "",
    artifacts: [],
    refreshNonce: 0,
    streamError: null,
    streamPaperId: null,
  };
}

function isAbortError(e: unknown): boolean {
  return (
    (e instanceof DOMException && e.name === "AbortError") ||
    (e instanceof Error && e.name === "AbortError")
  );
}

type StartStreamHooks = {
  onComplete: () => void;
};

type StreamJobsContextValue = {
  getJob: (conversationId: string) => JobSnapshot;
  generatingIds: string[];
  startStream: (conversationId: string, formData: FormData, hooks: StartStreamHooks) => void;
  abortJob: (conversationId: string) => void;
  clearStreamError: (conversationId: string) => void;
};

const StreamJobsContext = createContext<StreamJobsContextValue | null>(null);

export function StreamJobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<string, JobSnapshot>>({});
  const controllersRef = useRef<Map<string, AbortController>>(new Map());

  const getJob = useCallback(
    (conversationId: string): JobSnapshot => jobs[conversationId] ?? emptyJob(),
    [jobs],
  );

  const generatingIds = useMemo(
    () => Object.keys(jobs).filter((id) => jobs[id]?.busy),
    [jobs],
  );

  const abortJob = useCallback((conversationId: string) => {
    controllersRef.current.get(conversationId)?.abort();
    controllersRef.current.delete(conversationId);
    setJobs((prev) => {
      const cur = prev[conversationId];
      if (!cur) return prev;
      return {
        ...prev,
        [conversationId]: {
          ...cur,
          busy: false,
          streaming: "",
          statusHint: "",
        },
      };
    });
  }, []);

  const clearStreamError = useCallback((conversationId: string) => {
    setJobs((prev) => {
      const cur = prev[conversationId];
      if (!cur || !cur.streamError) return prev;
      return {
        ...prev,
        [conversationId]: { ...cur, streamError: null },
      };
    });
  }, []);

  const startStream = useCallback(
    (conversationId: string, formData: FormData, hooks: StartStreamHooks) => {
      controllersRef.current.get(conversationId)?.abort();
      const ac = new AbortController();
      controllersRef.current.set(conversationId, ac);
      const { signal } = ac;

      setJobs((prev) => ({
        ...prev,
        [conversationId]: {
          ...(prev[conversationId] ?? emptyJob()),
          busy: true,
          streaming: "",
          statusHint: "",
          artifacts: [],
          streamError: null,
          streamPaperId: null,
        },
      }));

      (async () => {
        let assistant = "";
        let failed = false;
        try {
          const res = await fetch(`${API}/api/chat/stream`, {
            method: "POST",
            body: formData,
            signal,
          });
          if (!res.ok) {
            throw new Error(`请求失败 (${res.status})`);
          }
          const reader = res.body?.getReader();
          const dec = new TextDecoder();
          let buf = "";
          if (!reader) throw new Error("无响应流");
          while (true) {
            const { done, value } = await reader.read();
            if (signal.aborted) break;
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const parts = buf.split("\n\n");
            buf = parts.pop() || "";
            for (const block of parts) {
              if (signal.aborted) break;
              const line = block.startsWith("data: ") ? block.slice(6) : block;
              if (!line.trim()) continue;
              let ev: { event?: string; data?: Record<string, unknown> };
              try {
                ev = JSON.parse(line);
              } catch {
                continue;
              }
              if (ev.event === "meta" && ev.data?.paper_id != null) {
                const pid = String(ev.data.paper_id);
                setJobs((prev) => {
                  const cur = prev[conversationId] ?? emptyJob();
                  if (!cur.busy) return prev;
                  return {
                    ...prev,
                    [conversationId]: { ...cur, streamPaperId: pid },
                  };
                });
              }
              if (ev.event === "status" && ev.data?.message) {
                setJobs((prev) => {
                  const cur = prev[conversationId] ?? emptyJob();
                  if (!cur.busy) return prev;
                  return {
                    ...prev,
                    [conversationId]: { ...cur, statusHint: String(ev.data!.message) },
                  };
                });
              }
              if (ev.event === "token" && ev.data?.t) {
                assistant += String(ev.data.t);
                const display = textForChatDisplay(assistant);
                setJobs((prev) => {
                  const cur = prev[conversationId] ?? emptyJob();
                  if (!cur.busy) return prev;
                  return {
                    ...prev,
                    [conversationId]: {
                      ...cur,
                      statusHint: "",
                      streaming: display,
                    },
                  };
                });
              }
              if (ev.event === "artifacts" && ev.data?.items) {
                setJobs((prev) => {
                  const cur = prev[conversationId] ?? emptyJob();
                  if (!cur.busy) return prev;
                  return {
                    ...prev,
                    [conversationId]: {
                      ...cur,
                      artifacts: ev.data!.items as StreamArtifact[],
                    },
                  };
                });
              }
              if (ev.event === "error" && ev.data?.message) {
                assistant += `\n⚠️ ${ev.data.message}`;
                const display = textForChatDisplay(assistant);
                setJobs((prev) => {
                  const cur = prev[conversationId] ?? emptyJob();
                  if (!cur.busy) return prev;
                  return {
                    ...prev,
                    [conversationId]: { ...cur, streaming: display, statusHint: "" },
                  };
                });
              }
            }
          }
        } catch (e) {
          if (!signal.aborted && !isAbortError(e)) {
            failed = true;
            const msg = e instanceof Error ? e.message : String(e);
            setJobs((prev) => {
              const cur = prev[conversationId] ?? emptyJob();
              return {
                ...prev,
                [conversationId]: {
                  ...cur,
                  busy: false,
                  streaming: "",
                  statusHint: "",
                  streamError: `请求失败：${msg}`,
                },
              };
            });
          }
        } finally {
          controllersRef.current.delete(conversationId);
          if (failed) return;
          if (signal.aborted) {
            setJobs((prev) => {
              const cur = prev[conversationId] ?? emptyJob();
              return {
                ...prev,
                [conversationId]: {
                  ...cur,
                  busy: false,
                  streaming: "",
                  statusHint: "",
                },
              };
            });
            return;
          }
          setJobs((prev) => {
            const cur = prev[conversationId] ?? emptyJob();
            return {
              ...prev,
              [conversationId]: {
                ...cur,
                busy: false,
                streaming: "",
                statusHint: "",
                refreshNonce: cur.refreshNonce + 1,
              },
            };
          });
          hooks.onComplete();
        }
      })();
    },
    [],
  );

  const value = useMemo(
    () => ({
      getJob,
      generatingIds,
      startStream,
      abortJob,
      clearStreamError,
    }),
    [getJob, generatingIds, startStream, abortJob, clearStreamError],
  );

  return <StreamJobsContext.Provider value={value}>{children}</StreamJobsContext.Provider>;
}

export function useStreamJobs(): StreamJobsContextValue {
  const ctx = useContext(StreamJobsContext);
  if (!ctx) throw new Error("useStreamJobs must be used within StreamJobsProvider");
  return ctx;
}
