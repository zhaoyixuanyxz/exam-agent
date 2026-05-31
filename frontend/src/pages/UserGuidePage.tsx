import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * 内容与仓库 docs/用户操作指南.md 一致，用于全站可读的流程说明。
 * 若更新文案，请同步该 markdown 与本文。
 * 视觉分层对齐工作台 / MultiPaper：白玻璃卡片、slate 主色、violet 链接与轻量强调。
 */
function Em({ children }: { children: ReactNode }) {
  return <span className="font-medium text-slate-800">{children}</span>;
}

const card = "rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-sm";
const cardHero = "rounded-2xl border border-white/60 bg-white/80 p-4 shadow-sm backdrop-blur";
const h3 = "text-sm font-semibold text-slate-800";
const h4Step = "text-xs font-medium uppercase tracking-wide text-slate-500";
const link = "text-violet-600 underline decoration-violet-200/80 underline-offset-2 hover:text-violet-800";
const tipsBox =
  "mt-2 rounded-xl border border-violet-100/90 bg-softlilac/50 py-2 pl-3 pr-2 text-slate-600 leading-relaxed";

export function UserGuidePage() {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-10 text-sm text-slate-600">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <header className={cardHero}>
          <h2 className="text-lg font-semibold tracking-tight text-slate-800">用户操作指南</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            面向老师 / 教研 / 自己试用：不讲术语堆砌，只讲
            <span className="text-slate-800">先干什么、后干什么、常见坑</span>。
          </p>
        </header>

        <section className={card} aria-labelledby="ug-section-1">
          <h3 id="ug-section-1" className={h3}>
            1. 顶栏五个 Tab 一句话
          </h3>
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200/80">
            <table className="w-full min-w-[480px] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/95">
                  <th className="px-3 py-2.5 font-medium text-slate-600">Tab</th>
                  <th className="px-3 py-2.5 font-medium text-slate-600">你可以把它理解成…</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-100 bg-white">
                  <td className="px-3 py-2">
                    <Link to="/workbench" className={link}>
                      工作台
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    <Em>加工车间</Em>：把试卷导进来、拆题、分析、出练习，主要干活都在这里。
                  </td>
                </tr>
                <tr className="border-b border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-2">
                    <Link to="/multi" className={link}>
                      多卷分析
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    <Em>对比报表</Em>：同一次备课里，拿<Em>至少两整套</Em>已经拆好的卷，看考点/题型/重复考点等
                    <Em>对比</Em>，不调大模型瞎编。
                  </td>
                </tr>
                <tr className="border-b border-slate-100 bg-white">
                  <td className="px-3 py-2">
                    <Link to="/question-bank" className={link}>
                      题库
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    <Em>成品货架</Em>：在系统里<Em>搜已经落库的题目</Em>，像逛题库，方便找题。
                  </td>
                </tr>
                <tr className="border-b border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-2">
                    <Link to="/governance" className={link}>
                      治理
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    <Em>质检台</Em>：给题目<Em>打审核状态</Em>（例如从「待审」到「已审」），让题库能长期用。
                  </td>
                </tr>
                <tr className="bg-white">
                  <td className="px-3 py-2">
                    <Link to="/org" className={link}>
                      组织
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    <Em>用户与留痕</Em>（偏管理）：<Em>换用户身份、看谁改了什么</Em>（审计），日常备课可以很少进来。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className={`${card} space-y-4`} aria-labelledby="ug-section-2">
          <h3 id="ug-section-2" className={h3}>
            2. 推荐主流程（第一次用，按这个来最顺）
          </h3>

          <div className="space-y-1.5">
            <h4 className={h4Step}>第 1 步：一定从「工作台」开始</h4>
            <ol className="ml-4 list-decimal space-y-1.5 marker:text-slate-400">
              <li>打开页面后，左边（若显示）是<Em>会话列表</Em>，相当于「这一趟备课 / 这一批活」的文件夹。</li>
              <li>
                上传或选中材料（试卷）→ 等 <Em>结构化</Em> 出结果 → 点<Em>确认结构化</Em>（名字可能略有不同，以界面为准）。
              </li>
              <li>
                <Em>只有确认成功，系统才认可「这道题正式进库」</Em>
                ，后面「题库」和「多卷分析」才有真数据可玩。
              </li>
            </ol>
            <div className={tipsBox}>
              <span className="font-medium text-violet-800/90">大白话</span>：没在工作台点「确认」，等于菜还没切好，后面货架和分析都没东西。
            </div>
          </div>

          <div className="space-y-1.5">
            <h4 className={h4Step}>第 2 步：看货 →「题库」Tab</h4>
            <ol className="ml-4 list-decimal space-y-1.5 marker:text-slate-400">
              <li>
                点顶栏 <Link to="/question-bank" className={link}>「题库」</Link>。
              </li>
              <li>用<Em>关键词</Em>搜题干，翻列表；点某一行，右边能看到摘要。</li>
              <li>这里适合：<Em>找题、看来源、和题目打交道</Em>，不必再回到聊天里翻长记录。</li>
            </ol>
            <div className={tipsBox}>
              <span className="font-medium text-violet-800/90">大白话</span>：工作台负责「生产」；题库负责「找做好的货」。
            </div>
          </div>

          <div className="space-y-1.5">
            <h4 className={h4Step}>第 3 步：比卷 →「多卷分析」Tab</h4>
            <ol className="ml-4 list-decimal space-y-1.5 marker:text-slate-400">
              <li>
                确保<Em>同一会话</Em>里，<Em>至少两整套材料</Em>都已经在上一步里<Em>完成结构化 + 确认</Em>。
              </li>
              <li>
                点 <Link to="/multi" className={link}>「多卷分析」</Link> → 勾选<Em>两份或以上</Em>材料 → 点运行分析。
              </li>
              <li>需要的话，界面上可勾选<Em>按标准考点统计</Em>（与考点主数据口径一致，适合教研）。</li>
            </ol>
            <div className={tipsBox}>
              <span className="font-medium text-violet-800/90">大白话</span>：单卷用工作台，<Em>两卷起谈对比</Em>用多卷分析。
            </div>
          </div>

          <div className="space-y-1.5">
            <h4 className={h4Step}>第 4 步：把关（可选）→「治理」Tab</h4>
            <ol className="ml-4 list-decimal space-y-1.5 marker:text-slate-400">
              <li>
                点 <Link to="/governance" className={link}>「治理」</Link>，列表里出现的是<Em>待你处理的题目</Em>（和「质量/审核」设计有关，若列表空，多半是库里暂无待处理项或尚未沉淀题目）。
              </li>
              <li>选题目，改<Em>审核状态</Em>并保存。</li>
            </ol>
            <div className={tipsBox}>
              <span className="font-medium text-violet-800/90">大白话</span>：题库能「用」，治理让题库「能管」。
            </div>
          </div>

          <div className="space-y-1.5">
            <h4 className={h4Step}>第 5 步：管身份（少用人少进）→「组织」Tab</h4>
            <ol className="ml-4 list-decimal space-y-1.5 marker:text-slate-400">
              <li>
                需要<Em>换测试账号 / 多用户</Em>时，可在这里改 <Em>X-User-Id</Em>（以界面说明为准）并<Em>应用</Em>。
              </li>
              <li>管理员可查看<Em>审计</Em>类信息，确认敏感操作有记录。</li>
            </ol>
            <div className={tipsBox}>
              <span className="font-medium text-violet-800/90">大白话</span>：普通老师日常<Em>可忽略</Em>；排查问题、验收时再进来。
            </div>
          </div>
        </section>

        <section className={card} aria-labelledby="ug-section-3">
          <h3 id="ug-section-3" className={h3}>
            3. 两个「最短路径」场景
          </h3>
          <ul className="mt-3 space-y-2.5 text-slate-600">
            <li className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-3">
              <span className="font-medium text-slate-800">场景 A：我只想把这套卷子变成题、能搜到</span>
              <p className="mt-1.5 text-sm text-slate-600">
                工作台上传 → 结构化 → <Em>确认</Em> → 去 <Link to="/question-bank" className={link}>「题库」</Link> 搜一搜。
              </p>
            </li>
            <li className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-3">
              <span className="font-medium text-slate-800">场景 B：我有两套卷，想看考点差异</span>
              <p className="mt-1.5 text-sm text-slate-600">
                两卷都在 <Link to="/workbench" className={link}>工作台</Link> 里分别走通结构化 + <Em>确认</Em> →{" "}
                <Link to="/multi" className={link}>「多卷分析」</Link> 勾两卷 → 出结果。
              </p>
            </li>
          </ul>
        </section>

        <section className={card} aria-labelledby="ug-section-4">
          <h3 id="ug-section-4" className={h3}>
            4. 常见问题（一看就懂）
          </h3>
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200/80">
            <table className="w-full min-w-[520px] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/95">
                  <th className="px-3 py-2.5 font-medium text-slate-600">现象</th>
                  <th className="px-3 py-2.5 font-medium text-slate-600">常见原因</th>
                  <th className="px-3 py-2.5 font-medium text-slate-600">你可以怎么做</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-100 bg-white">
                  <td className="px-3 py-2 align-top font-medium text-slate-800">题库是空的，或很冷清</td>
                  <td className="px-3 py-2 align-top text-slate-500">还没「确认」结构化，或没做过几套卷</td>
                  <td className="px-3 py-2 align-top text-slate-600">
                    回 <Link to="/workbench" className={link}>工作台</Link> 把材料确认；多确认几份就有积累
                  </td>
                </tr>
                <tr className="border-b border-slate-100 bg-slate-50/50">
                  <td className="px-3 py-2 align-top font-medium text-slate-800">多卷分析说有效卷不足 2 份</td>
                  <td className="px-3 py-2 align-top text-slate-500">同一会话里确认过的卷不够 2 份，或筛选把卷筛掉了</td>
                  <td className="px-3 py-2 align-top text-slate-600">少勾筛选，或再确认一试卷</td>
                </tr>
                <tr className="border-b border-slate-100 bg-white">
                  <td className="px-3 py-2 align-top font-medium text-slate-800">治理里没有题</td>
                  <td className="px-3 py-2 align-top text-slate-500">当前没有待你处理的那类状态</td>
                  <td className="px-3 py-2 align-top text-slate-600">有题进库、且流程设计会往治理送时才会有</td>
                </tr>
                <tr className="bg-slate-50/50">
                  <td className="px-3 py-2 align-top font-medium text-slate-800">多卷和题库跟聊天不一样</td>
                  <td className="px-3 py-2 align-top text-slate-500">聊天偏对话；Tab 偏「把数据当资产管」</td>
                  <td className="px-3 py-2 align-top text-slate-600">以 Tab 为主走流程</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className={card} aria-labelledby="ug-section-5">
          <h3 id="ug-section-5" className={h3}>
            5. 和文档、验收的关系
          </h3>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-slate-400">
            <li>
              技术说明与 API 见：仓库{" "}
              <code className="rounded-lg border border-slate-200 bg-mist px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
                docs/V2_3_audit_and_acceptance.md
              </code>
            </li>
            <li>
              任务与进度见：仓库{" "}
              <code className="rounded-lg border border-slate-200 bg-mist px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
                new/V2.3任务表.md
              </code>
            </li>
          </ul>
          <p className="mt-2 text-slate-600">
            有产品或培训需要时，可在此文档基础上加<Em>截图位</Em>、<Em>本校本学科示例</Em>，不影响开发阅读。
          </p>
        </section>

        <p className="px-1 text-center text-xs text-slate-500">文档版本：与 V2.3 产品化（题库 / 多卷 / 治理 / 组织）配套；若界面文案变更，以实际界面为准。</p>
      </div>
    </div>
  );
}
