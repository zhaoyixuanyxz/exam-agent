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
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-10 text-sm text-slate-700">
      <div className="mx-auto flex max-w-3xl flex-col gap-3">
        <div className="rounded-2xl border border-white/60 bg-white/80 p-4 shadow-sm backdrop-blur">
          <h2 className="text-base font-semibold text-slate-800">组织与权限</h2>
          <p className="mt-1 text-sm text-slate-600">切换当前请求使用的用户标识，并查看审计留痕（需权限）。</p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-600">X-User-Id</span>
            <input
              className="min-w-[240px] rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-800 shadow-sm"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
            <button
              type="button"
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-slate-800 shadow-sm hover:bg-slate-50"
              onClick={() => {
                localStorage.setItem("exam-agent-user-id", userId);
                setErr(null);
                setMe(null);
                setLogs(null);
                window.location.reload();
              }}
            >
              应用并刷新
            </button>
          </div>
          {err && <p className="mt-2 text-xs text-amber-800">{err}</p>}
          {me && (
            <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/80 p-3 text-xs text-slate-700">
              <p>用户: {me.display_name || me.id}</p>
              <p className="mt-0.5">角色: {me.role} · 数据范围: {me.data_scope}</p>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-800">审计（管理员）</h3>
          {logs && logs.length > 0 ? (
            <ul className="mt-2 space-y-1.5 text-xs text-slate-600">
              {logs.map((l) => (
                <li
                  key={l.id}
                  className="rounded-lg border border-slate-100 bg-slate-50/80 px-2 py-1.5 text-slate-700"
                >
                  {l.created_at} · {l.action} · {l.resource_type} · {l.user_id.slice(0, 8)}…
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-slate-500">无数据或非管理员。默认用户为 admin 可调审计。</p>
          )}
        </div>
      </div>
    </div>
  );
}
