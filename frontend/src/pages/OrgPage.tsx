import { useEffect, useState } from "react";
import { apiGet, DEFAULT_USER } from "../api/client";

type Me = { id: string; display_name: string; role: string; data_scope: string };
type Log = { id: string; action: string; resource_type: string; user_id: string; created_at?: string | null };

export function OrgPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [logs, setLogs] = useState<Log[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [userId, setUserId] = useState(() => localStorage.getItem("exam-agent-user-id") || DEFAULT_USER);

  useEffect(() => {
    void (async () => {
      setErr(null);
      try {
        const m = await apiGet<Me>("/api/me");
        setMe(m);
        const l = await apiGet<Log[]>("/api/audit-logs", { limit: 50 });
        setLogs(l);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
        setLogs(null);
      }
    })();
  }, [userId]);

  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3 text-sm text-slate-800">
      <h2 className="text-base font-semibold">组织与权限</h2>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-slate-600">X-User-Id</span>
        <input
          className="min-w-[240px] rounded border border-slate-200 px-2 py-1 font-mono text-xs"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <button
          type="button"
          className="rounded border border-slate-200 bg-white px-2 py-1"
          onClick={() => {
            localStorage.setItem("exam-agent-user-id", userId);
            setErr(null);
            void 0; // re-trigger: force reload by setState
            setMe(null);
            setLogs(null);
            window.location.reload();
          }}
        >
          应用并刷新
        </button>
      </div>
      {err && <p className="text-xs text-amber-700">{err}</p>}
      {me && (
        <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs">
          <p>用户: {me.display_name || me.id}</p>
          <p>角色: {me.role} · 数据范围: {me.data_scope}</p>
        </div>
      )}
      <h3 className="font-medium">审计（管理员）</h3>
      {logs && logs.length > 0 ? (
        <ul className="space-y-1 text-xs text-slate-600">
          {logs.map((l) => (
            <li key={l.id} className="rounded border border-slate-100 bg-white p-1">
              {l.created_at} · {l.action} · {l.resource_type} · {l.user_id.slice(0, 8)}…
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-500">无数据或非管理员。默认用户为 admin 可调审计。</p>
      )}
    </div>
  );
}
