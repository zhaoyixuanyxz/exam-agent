"""V2.2：多卷确定性聚合分析（无跨卷 LLM）。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.models import ExamPaper, KnowledgeKeyMapping, KnowledgePointCanonical
from app.db.sync_session import sync_session
from app.models.schemas import (
    ChapterDistributionSlice,
    ChapterHintCount,
    KnowledgeAnalysisResult,
    KnowledgeCoverageDiff,
    KnowledgeCoveragePaperSlice,
    MultiPaperAnalysisRequest,
    MultiPaperAnalysisResponse,
    PaperSummaryInAnalysis,
    QuestionTypeCount,
    QuestionTypeDistributionSlice,
    RepeatedKnowledgePoint,
)
from app.services.question_assets import load_question_assets_or_build


def _alignment_matches_filter(paper: ExamPaper, req: MultiPaperAnalysisRequest) -> bool:
    a = paper.alignment_json
    if not isinstance(a, dict):
        a = {}
    if req.subject:
        subj = str(a.get("subject") or "").strip()
        if subj != str(req.subject).strip():
            return False
    if req.grade_contains:
        g = str(req.grade_contains).strip()
        gmin = str(a.get("grade_min") or "")
        gmax = str(a.get("grade_max") or "")
        if g and g not in gmin and g not in gmax:
            return False
    return True


def _parse_iso_dt(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    raw = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _date_in_range(paper: ExamPaper, req: MultiPaperAnalysisRequest) -> bool:
    ca = _parse_iso_dt(req.created_after)
    cb = _parse_iso_dt(req.created_before)
    if not ca and not cb:
        return True
    t = paper.created_at
    if t is None:
        return True
    if ca and t < ca:
        return False
    if cb and t > cb:
        return False
    return True


def _knowledge_point_name_map(paper: ExamPaper) -> dict[str, str]:
    raw = paper.knowledge_analysis_json
    if not raw or not isinstance(raw, dict):
        return {}
    try:
        ka = KnowledgeAnalysisResult.model_validate(raw)
    except Exception:
        return {}
    return {kp.key: kp.name for kp in ka.knowledge_points}


def _chapter_hint_by_key(paper: ExamPaper) -> dict[str, str]:
    raw = paper.knowledge_analysis_json
    if not raw or not isinstance(raw, dict):
        return {}
    try:
        ka = KnowledgeAnalysisResult.model_validate(raw)
    except Exception:
        return {}
    return {kp.key: (kp.book_chapter_hint or "").strip() for kp in ka.knowledge_points}


def _resolved_keys(
    session: Any,
    row: Any,
    paper: ExamPaper,
    use_canonical: bool,
) -> list[str]:
    raw_list = [str(k).strip() for k in (row.knowledge_point_keys_json or []) if k and str(k).strip()]
    if not use_canonical:
        return raw_list
    out: list[str] = []
    for r in raw_list:
        m = session.execute(
            select(KnowledgeKeyMapping).where(KnowledgeKeyMapping.raw_key == r)
        ).scalar_one_or_none()
        if m:
            kpc = session.get(KnowledgePointCanonical, str(m.knowledge_point_id))
            out.append(str(kpc.standard_key) if kpc else r)
        else:
            out.append(r)
    return out


def _kp_display_name(
    session: Any,
    key: str,
    use_canonical: bool,
    fallback: str,
) -> str:
    if not use_canonical:
        return fallback
    m = session.execute(
        select(KnowledgeKeyMapping).where(KnowledgeKeyMapping.raw_key == key)
    ).scalar_one_or_none()
    if m:
        kpc = session.get(KnowledgePointCanonical, str(m.knowledge_point_id))
        if kpc and (kpc.name or "").strip():
            return str(kpc.name).strip()
    return fallback


def run_multi_paper_analysis(
    conversation_id: str,
    req: MultiPaperAnalysisRequest,
) -> MultiPaperAnalysisResponse:
    notes: list[str] = []
    with sync_session() as session:
        papers: list[ExamPaper] = []
        subset = set(req.paper_id_subset) if req.paper_id_subset else None
        for pid in req.paper_ids:
            p = session.get(ExamPaper, pid)
            if not p or p.conversation_id != conversation_id:
                continue
            if subset is not None and p.id not in subset:
                notes.append(f"材料 {pid[:8]}… 已按来源子集排除")
                continue
            if not _date_in_range(p, req):
                notes.append(f"材料 {pid[:8]}… 已按时间范围排除")
                continue
            if not _alignment_matches_filter(p, req):
                notes.append(f"材料 {pid[:8]}… 已按对齐信息过滤排除")
                continue
            papers.append(p)
        # 保持请求中的顺序（去重后首次出现顺序）
        seen: set[str] = set()
        ordered: list[ExamPaper] = []
        for p in papers:
            if p.id in seen:
                continue
            seen.add(p.id)
            ordered.append(p)
        papers = ordered
        if len(papers) < 2:
            raise ValueError("有效材料不足 2 份（请检查 id 是否属于本会话，或放宽筛选条件）")

        # 每卷题目行
        assets_by_paper: dict[str, list[Any]] = {}
        summaries: list[PaperSummaryInAnalysis] = []
        all_key_sets: list[set[str]] = []
        kp_names_global: dict[str, str] = {}
        chapter_by_paper: dict[str, dict[str, str]] = {}
        use_c = bool(req.use_canonical_knowledge_points)

        for p in papers:
            rows = load_question_assets_or_build(session, p)
            if not rows and (p.structured_confirm_status or "") == "confirmed":
                notes.append(
                    f"材料「{p.display_name or p.id[:8]}」暂无题目资产行，请检查结构化 JSON",
                )
            assets_by_paper[p.id] = rows
            sp_title = ""
            if p.parsed_json and isinstance(p.parsed_json, dict):
                sp_title = str(p.parsed_json.get("title") or "").strip()
            ka_count = 0
            if p.knowledge_analysis_json and isinstance(p.knowledge_analysis_json, dict):
                try:
                    ka = KnowledgeAnalysisResult.model_validate(p.knowledge_analysis_json)
                    ka_count = len(ka.knowledge_points)
                except Exception:
                    notes.append(f"材料「{p.display_name or p.id[:8]}」考点分析 JSON 不可用，部分维度为空")
            summaries.append(
                PaperSummaryInAnalysis(
                    paper_id=p.id,
                    display_name=p.display_name,
                    structured_title=sp_title,
                    structured_version=int(p.structured_version or 0),
                    question_count=len(rows),
                    knowledge_point_count=ka_count,
                ),
            )
            ks: set[str] = set()
            for row in rows:
                for rk in _resolved_keys(session, row, p, use_c):
                    if rk:
                        ks.add(rk)
            all_key_sets.append(ks)
            name_map = _knowledge_point_name_map(p)
            for row in rows:
                for raw in row.knowledge_point_keys_json or []:
                    raw = str(raw).strip()
                    if not raw:
                        continue
                    for std in _resolved_keys(
                        session,
                        type("R", (), {"knowledge_point_keys_json": [raw]})(),
                        p,
                        use_c,
                    ):
                        if not std:
                            continue
                        disp = _kp_display_name(session, raw, use_c, name_map.get(raw, ""))
                        if std not in kp_names_global or not (kp_names_global.get(std) or "").strip():
                            kp_names_global[std] = disp
            ch_raw = _chapter_hint_by_key(p)
            if use_c:
                chm: dict[str, str] = {}
                for raw_key, h in ch_raw.items():
                    if not h:
                        continue
                    m = session.execute(
                        select(KnowledgeKeyMapping).where(KnowledgeKeyMapping.raw_key == raw_key)
                    ).scalar_one_or_none()
                    if m:
                        kpc = session.get(KnowledgePointCanonical, str(m.knowledge_point_id))
                        sk = str(kpc.standard_key) if kpc else raw_key
                    else:
                        sk = raw_key
                    chm[sk] = h
                chapter_by_paper[p.id] = chm
            else:
                chapter_by_paper[p.id] = ch_raw

        union_keys: set[str] = set()
        for s in all_key_sets:
            union_keys |= s
        common = set.intersection(*all_key_sets) if all_key_sets else set()

        per_paper_slices: list[KnowledgeCoveragePaperSlice] = []
        for i, p in enumerate(papers):
            ks = all_key_sets[i]
            others_union: set[str] = set()
            for j, s2 in enumerate(all_key_sets):
                if j != i:
                    others_union |= s2
            unique_vs = sorted(ks - others_union)
            per_paper_slices.append(
                KnowledgeCoveragePaperSlice(
                    paper_id=p.id,
                    display_name=p.display_name,
                    knowledge_point_keys=sorted(ks),
                    unique_vs_others=unique_vs,
                ),
            )

        # 题型分布
        qdist: list[QuestionTypeDistributionSlice] = []
        for p in papers:
            ctr: Counter[str] = Counter()
            for row in assets_by_paper.get(p.id, []):
                qt = (row.qtype or "").strip() or "（未标注）"
                ctr[qt] += 1
            qdist.append(
                QuestionTypeDistributionSlice(
                    paper_id=p.id,
                    display_name=p.display_name,
                    counts=[
                        QuestionTypeCount(qtype=k, count=v)
                        for k, v in sorted(ctr.items(), key=lambda x: (-x[1], x[0]))
                    ],
                ),
            )

        # 重复考点：在至少两卷出现的 key
        key_paper_count: dict[str, set[str]] = defaultdict(set)
        key_q_hits: Counter[str] = Counter()
        for p in papers:
            for row in assets_by_paper.get(p.id, []):
                for kk in _resolved_keys(session, row, p, use_c):
                    if not kk:
                        continue
                    key_paper_count[kk].add(p.id)
                    key_q_hits[kk] += 1
        repeated: list[RepeatedKnowledgePoint] = []
        for key, pset in sorted(key_paper_count.items(), key=lambda x: (-len(x[1]), x[0])):
            if len(pset) < 2:
                continue
            repeated.append(
                RepeatedKnowledgePoint(
                    knowledge_point_key=key,
                    name=kp_names_global.get(key, ""),
                    paper_count=len(pset),
                    total_question_hits=key_q_hits[key],
                ),
            )

        # 章节分布（book_chapter_hint）
        chap_dist: list[ChapterDistributionSlice] = []
        for p in papers:
            ch_ctr: Counter[str] = Counter()
            chmap = chapter_by_paper.get(p.id, {}) or {}
            for row in assets_by_paper.get(p.id, []):
                for raw in row.knowledge_point_keys_json or []:
                    rks = str(raw).strip()
                    if not rks:
                        continue
                    for rk in _resolved_keys(
                        session,
                        type("R", (), {"knowledge_point_keys_json": [rks]})(),
                        p,
                        use_c,
                    ):
                        hint = chmap.get(rk, "")
                        if not hint and not use_c:
                            hint = chmap.get(rks, "")
                        if hint:
                            ch_ctr[hint] += 1
            chap_dist.append(
                ChapterDistributionSlice(
                    paper_id=p.id,
                    display_name=p.display_name,
                    chapters=[
                        ChapterHintCount(hint=h, count=c)
                        for h, c in sorted(ch_ctr.items(), key=lambda x: (-x[1], x[0]))
                    ],
                ),
            )

        return MultiPaperAnalysisResponse(
            conversation_id=conversation_id,
            paper_summaries=summaries,
            knowledge_coverage_diff=KnowledgeCoverageDiff(
                per_paper=per_paper_slices,
                common_across_selected=sorted(common),
            ),
            question_type_distribution=qdist,
            repeated_knowledge_points=repeated,
            chapter_distribution=chap_dist,
            notes=notes,
        )
