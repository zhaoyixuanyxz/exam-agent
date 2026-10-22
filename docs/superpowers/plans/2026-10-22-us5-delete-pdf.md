# US-5 删除库内 PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 老师在「生成文件」里各删各的 PDF；删完列表没了、文件打不开，题目和考点还在，还可以再生成被删的那一份。

**Architecture:** 单独一个删除函数：去掉磁盘上的这份 PDF 和这条产物记录，不碰题目。考点说明用试卷上的隐藏标记，避免删 PDF 后 Markdown 又挂回列表。HTTP 删除接到这个函数。前端在每一条旁边确认后调用。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、pytest、React 18。

---

## File map

- Create: `backend/app/services/artifact_delete.py` — 删一份 PDF、隐藏考点说明、不碰题目。
- Create: `backend/tests/test_artifact_delete.py`
- Modify: `backend/app/db/models.py` — `ExamPaper.knowledge_explanation_hidden`
- Modify: `backend/app/db/migrate.py` 与 `backend/app/db/init_db.py` — 给已有库加这一列。
- Modify: `backend/app/api/chat.py` — 删除接口；列表不展示已删的；缺失文件不列出。
- Modify: `backend/app/agent/tools.py` — 再生成只补被删的那一份；考点分析成功后重新显示考点说明。
- Modify: `frontend/src/components/ArtifactCenter.tsx` 与 `frontend/src/components/Chat.tsx` — 每条旁边删除并确认。
- Do not change `conversation_delete.py`. Do not unlink Markdown. Do not delete `QuestionAsset`.

实现从当前 `main` 拉分支。不要依赖尚未合并的 US-2、US-3 或 US-4 分支。`knowledge_pdf` 这一 kind 在删除函数里按产物记录处理，US-4 合并后同一条删除仍然有效。

### Task 1: 删 PDF 文件和产物记录，题目还在

**Files:**
- Create: `backend/app/services/artifact_delete.py`
- Test: `backend/tests/test_artifact_delete.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models import Artifact, ExamPaper, QuestionAsset
from app.db.sync_session import sync_session
from app.main import app
from app.services.artifact_delete import PDF_KINDS, delete_stored_pdf
from app.services.storage import export_dir_for_conversation


def _write_pdf(cid: str, name: str, body: bytes = b"%PDF-1.4") -> Path:
    path = export_dir_for_conversation(cid) / name
    path.write_bytes(body)
    return path


def test_delete_stored_pdf_unlinks_file_keeps_questions():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _write_pdf(cid, "practice_kp_a.pdf", b"%PDF-1.4 keep-me")
        other = _write_pdf(cid, "practice_kp_a_answers.pdf", b"%PDF-1.4 other")
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            qa = QuestionAsset(
                conversation_id=cid,
                paper_id=paper.id,
                question_order=1,
                stem="二次函数顶点",
                knowledge_point_keys_json=["kp_a"],
            )
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
                display_name="练习卷",
            )
            other_art = Artifact(
                paper_id=paper.id,
                kind="pdf_answer",
                path=other.as_posix(),
                knowledge_point_key="kp_a",
                display_name="参考答案",
            )
            s.add_all([qa, art, other_art])
            s.commit()
            paper_id = paper.id
            art_id = art.id
            other_id = other_art.id
            qa_id = qa.id
        with sync_session() as s:
            row = s.get(Artifact, art_id)
            delete_stored_pdf(s, row)
            s.commit()
        assert pdf.is_file() is False
        assert other.is_file() is True
        with sync_session() as s:
            assert s.get(Artifact, art_id) is None
            assert s.get(Artifact, other_id) is not None
            kept = s.get(QuestionAsset, qa_id)
            assert kept is not None
            assert kept.stem == "二次函数顶点"
            assert s.get(ExamPaper, paper_id) is not None
    assert "pdf_question" in PDF_KINDS
    assert "pdf_answer" in PDF_KINDS
    assert "knowledge_pdf" in PDF_KINDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py::test_delete_stored_pdf_unlinks_file_keeps_questions -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.artifact_delete'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Delete one stored PDF artifact without touching questions or other files."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Artifact, ExamPaper
from app.services.practice_path_security import resolve_under_data_dir

PDF_KINDS = frozenset({"pdf_question", "pdf_answer", "knowledge_pdf"})


def delete_stored_pdf(session: Session, artifact: Artifact) -> None:
    raw = (artifact.path or "").strip()
    if raw:
        resolved = resolve_under_data_dir(raw)
        target = resolved if resolved is not None else None
        if target is not None:
            target.unlink(missing_ok=True)
    if artifact.kind == "knowledge_pdf":
        paper = session.get(ExamPaper, artifact.paper_id)
        if paper is not None:
            paper.knowledge_explanation_hidden = True
            session.add(paper)
    session.delete(artifact)
```

`ExamPaper.knowledge_explanation_hidden` is added in Task 2. For this task, either add a `getattr` fallback:

```python
        if paper is not None:
            setattr(paper, "knowledge_explanation_hidden", True)
            session.add(paper)
```

or add the column in this same commit if the test import of `delete_stored_pdf` otherwise fails. Prefer adding the column in Task 2; use `setattr` here so Task 1 stays about unlink + drop row.

If `unlink` raises `OSError`, do not `session.delete`. Let it propagate.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py::test_delete_stored_pdf_unlinks_file_keeps_questions -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/artifact_delete.py backend/tests/test_artifact_delete.py
git commit -m "feat: delete one practice PDF without removing questions"
```

### Task 2: 考点说明删了不退回 Markdown；文件已不在仍去掉记录

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/migrate.py`
- Modify: `backend/app/db/init_db.py`
- Modify: `backend/app/services/artifact_delete.py`
- Modify: `backend/app/api/chat.py` `_list_artifacts_sync`
- Test: `backend/tests/test_artifact_delete.py`

- [ ] **Step 1: Write the failing test**

```python
from app.services.artifact_delete import hide_knowledge_explanation
from app.api.chat import _list_artifacts_sync


def test_hide_knowledge_explanation_keeps_markdown_file():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        out = export_dir_for_conversation(cid)
        md = out / "考点说明_x.md"
        md.write_text("# 说明", encoding="utf-8")
        pdf = _write_pdf(cid, "考点说明_x.pdf")
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(paper)
            s.flush()
            art = Artifact(
                paper_id=paper.id,
                kind="knowledge_pdf",
                path=pdf.as_posix(),
                display_name="考点说明",
            )
            s.add(art)
            s.commit()
            paper_id = paper.id
            art_id = art.id
        with sync_session() as s:
            hide_knowledge_explanation(s, s.get(ExamPaper, paper_id))
            delete_stored_pdf(s, s.get(Artifact, art_id))
            s.commit()
        assert md.is_file() is True
        assert pdf.is_file() is False
        items = _list_artifacts_sync(cid)
        kinds = [i["kind"] for i in items]
        assert "markdown" not in kinds
        assert "knowledge_pdf" not in kinds


def test_delete_missing_file_still_drops_artifact():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        missing = export_dir_for_conversation(cid) / "gone.pdf"
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_answer",
                path=missing.as_posix(),
                knowledge_point_key="kp_a",
            )
            s.add(art)
            s.commit()
            art_id = art.id
        with sync_session() as s:
            delete_stored_pdf(s, s.get(Artifact, art_id))
            s.commit()
        with sync_session() as s:
            assert s.get(Artifact, art_id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py::test_hide_knowledge_explanation_keeps_markdown_file tests/test_artifact_delete.py::test_delete_missing_file_still_drops_artifact -v`

Expected: FAIL with `ImportError: cannot import name 'hide_knowledge_explanation'` or missing `knowledge_explanation_hidden`

- [ ] **Step 3: Write minimal implementation**

On `ExamPaper` after `knowledge_markdown_path`:

```python
    knowledge_explanation_hidden: Mapped[bool] = mapped_column(default=False)
```

In `migrate.py`:

```python
def apply_sqlite_exam_paper_knowledge_explanation_hidden(connection: Connection) -> None:
    insp = inspect(connection)
    if not insp.has_table("exam_papers"):
        return
    cols = {c["name"] for c in insp.get_columns("exam_papers")}
    if "knowledge_explanation_hidden" not in cols:
        connection.execute(
            text(
                "ALTER TABLE exam_papers ADD COLUMN knowledge_explanation_hidden BOOLEAN DEFAULT 0"
            )
        )
```

Call it from `init_db.py` next to the other `apply_sqlite_exam_paper_*` functions.

In `artifact_delete.py` add:

```python
def hide_knowledge_explanation(session: Session, paper: ExamPaper) -> None:
    paper.knowledge_explanation_hidden = True
    session.add(paper)
```

Replace the `setattr` in `delete_stored_pdf` with `paper.knowledge_explanation_hidden = True`.

In `_list_artifacts_sync`, skip the Markdown block when `p.knowledge_explanation_hidden` is true. For Artifact rows, skip when `a.path` is missing or `Path(a.path).is_file()` is false.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrate.py backend/app/db/init_db.py backend/app/services/artifact_delete.py backend/app/api/chat.py backend/tests/test_artifact_delete.py
git commit -m "feat: hide knowledge notes after the explanation PDF is deleted"
```

### Task 3: HTTP 删除接到「生成文件」

**Files:**
- Modify: `backend/app/api/chat.py`
- Test: `backend/tests/test_artifact_delete.py`

- [ ] **Step 1: Write the failing test**

```python
def test_delete_artifact_endpoint_removes_list_item():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _write_pdf(cid, "q.pdf")
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            qa = QuestionAsset(
                conversation_id=cid,
                paper_id=paper.id,
                question_order=1,
                stem="还在",
            )
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
            )
            s.add_all([qa, art])
            s.commit()
            art_id = art.id
            qa_id = qa.id
        listed = client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        assert any(i["id"] == art_id for i in listed)
        rd = client.delete(f"/api/conversations/{cid}/artifacts/{art_id}")
        assert rd.status_code == 200
        assert rd.json() == {"ok": True}
        assert pdf.is_file() is False
        listed2 = client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        assert all(i["id"] != art_id for i in listed2)
        with sync_session() as s:
            assert s.get(QuestionAsset, qa_id) is not None


def test_delete_markdown_slot_hides_without_unlinking():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        md = export_dir_for_conversation(cid) / "考点说明_p.md"
        md.write_text("旧稿", encoding="utf-8")
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(paper)
            s.commit()
            paper_id = paper.id
        rd = client.delete(f"/api/conversations/{cid}/artifacts/md:{paper_id}")
        assert rd.status_code == 200
        assert md.read_text(encoding="utf-8") == "旧稿"
        kinds = [
            i["kind"]
            for i in client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        ]
        assert "markdown" not in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py::test_delete_artifact_endpoint_removes_list_item -v`

Expected: FAIL with 405 or 404 (no DELETE route)

- [ ] **Step 3: Write minimal implementation**

```python
@router.delete("/conversations/{conversation_id}/artifacts/{artifact_id}")
async def delete_conversation_artifact(
    conversation_id: str,
    artifact_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    try:
        _delete_conversation_artifact_sync(conversation_id, artifact_id)
    except FileNotFoundError:
        raise HTTPException(404, "artifact not found") from None
    except OSError:
        return {"ok": False, "error": "删除失败，请稍后重试"}
    return {"ok": True}


def _delete_conversation_artifact_sync(conversation_id: str, artifact_id: str) -> None:
    from app.services.artifact_delete import delete_stored_pdf, hide_knowledge_explanation

    with sync_session() as s:
        if artifact_id.startswith("md:"):
            paper_id = artifact_id[3:]
            paper = s.get(ExamPaper, paper_id)
            if paper is None or paper.conversation_id != conversation_id:
                raise FileNotFoundError
            hide_knowledge_explanation(s, paper)
            s.commit()
            return
        art = s.get(Artifact, artifact_id)
        if art is None:
            raise FileNotFoundError
        paper = s.get(ExamPaper, art.paper_id)
        if paper is None or paper.conversation_id != conversation_id:
            raise FileNotFoundError
        if art.kind not in PDF_KINDS:
            raise FileNotFoundError
        delete_stored_pdf(s, art)
        s.commit()
```

Import `PDF_KINDS` from `artifact_delete`. On `OSError`, do not commit. Do not put the exception text, stack, or paper body in the JSON.

If `_list_artifacts_sync` still lists artifacts whose files are gone, skip those rows here (Task 2 already required this).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py -v`

Expected: PASS. Also run `pytest tests/test_api.py::test_messages_and_delete_conversation -v` — still PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/test_artifact_delete.py
git commit -m "feat: delete a library PDF from the artifacts API"
```

### Task 4: 再生成只补被删的那一份；分析成功后考点说明回来

**Files:**
- Modify: `backend/app/agent/tools.py` `_generate_chunk_practice_pdf_for_kp` and `run_knowledge_analysis`
- Test: `backend/tests/test_artifact_delete.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from unittest.mock import patch

from app.agent.tools import _generate_chunk_practice_pdf_for_kp
from app.models.schemas import KnowledgePointItem


def test_practice_regenerate_fills_only_missing_kind(tmp_path: Path):
    q_pdf = tmp_path / "practice_kp_a.pdf"
    q_pdf.write_bytes(b"%PDF-1.4 question")
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_analysis_json={
                    "theme_title": "t",
                    "knowledge_points": [
                        {
                            "key": "kp_a",
                            "name": "顶点式",
                            "summary": "s",
                            "book_chapter_hint": "",
                        }
                    ],
                    "mappings": [],
                },
                alignment_json={"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
            )
            s.add(paper)
            s.flush()
            s.add(
                Artifact(
                    paper_id=paper.id,
                    kind="pdf_question",
                    path=q_pdf.as_posix(),
                    knowledge_point_key="kp_a",
                )
            )
            s.commit()
            paper_id = paper.id
        calls = {"q": 0, "a": 0}

        def fake_q(*_a, **_k):
            calls["q"] += 1

        def fake_a(*_a, **_k):
            calls["a"] += 1
            Path(_a[1]).write_bytes(b"%PDF-1.4 answers")

        with (
            patch("app.agent.tools.generate_practice_set") as gen,
            patch("app.agent.tools.render_practice_pdf", side_effect=fake_q),
            patch("app.agent.tools.render_answer_pdf", side_effect=fake_a),
            patch("app.agent.tools.export_dir_for_conversation", return_value=tmp_path),
        ):
            gen.return_value = type("P", (), {"knowledge_point_key": "", "knowledge_point_name": ""})()
            with sync_session() as s:
                paper = s.get(ExamPaper, paper_id)
                kp = KnowledgePointItem(key="kp_a", name="顶点式", summary="s", book_chapter_hint="")
                err = _generate_chunk_practice_pdf_for_kp(
                    s,
                    paper,
                    kp,
                    10,
                    use_original_figures=False,
                    include_figures=True,
                    difficulty="medium",
                    question_types_json="[]",
                    output_mode="questions_and_answers",
                )
                assert err is None
                s.commit()
        assert calls["q"] == 0
        assert calls["a"] == 1
        assert q_pdf.read_bytes() == b"%PDF-1.4 question"


def test_run_knowledge_analysis_clears_hidden_flag(monkeypatch):
    from app.agent.tools import run_knowledge_analysis
    from app.models.schemas import KnowledgeAnalysisResult, KnowledgePointItem

    def fake_analyze(_summary, _align):
        return KnowledgeAnalysisResult(
            theme_title="二次函数",
            knowledge_points=[
                KnowledgePointItem(key="kp_a", name="顶点式", summary="配方法求顶点", book_chapter_hint=""),
            ],
            mappings=[],
        )

    monkeypatch.setattr("app.agent.tools.analyze_knowledge", fake_analyze)
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                parsed_json={
                    "title": "卷",
                    "sections": [
                        {
                            "title": "一",
                            "questions": [
                                {
                                    "order_index": 1,
                                    "qtype": "填空",
                                    "stem": "题",
                                    "options": [],
                                    "blocks": [],
                                }
                            ],
                        }
                    ],
                },
                structured_confirm_status="confirmed",
                alignment_json={"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
                knowledge_explanation_hidden=True,
            )
            s.add(paper)
            s.commit()
            paper_id = paper.id
        msg = run_knowledge_analysis(paper_id)
        assert str(msg).startswith("成功")
        with sync_session() as s:
            assert s.get(ExamPaper, paper_id).knowledge_explanation_hidden is False
```

Do not call the live model. After a successful `run_knowledge_analysis`, `knowledge_explanation_hidden` must be `False`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py::test_practice_regenerate_fills_only_missing_kind -v`

Expected: FAIL because `render_practice_pdf` is still called (or `generate_practice_set` is reached without skip)

- [ ] **Step 3: Write minimal implementation**

In `tools.py`, before rendering in `_generate_chunk_practice_pdf_for_kp`:

```python
def _artifact_file_present(paper: ExamPaper, kind: str, kp_key: str) -> bool:
    for a in paper.artifacts or []:
        if a.kind != kind:
            continue
        if (a.knowledge_point_key or "") != kp_key:
            continue
        if a.path and Path(a.path).is_file():
            return True
    return False
```

```python
    q_exists = _artifact_file_present(paper, "pdf_question", kp.key)
    a_exists = _artifact_file_present(paper, "pdf_answer", kp.key)
    fill_only_missing = q_exists != a_exists
    skip_q = bool(fill_only_missing and q_exists)
    skip_a = bool(fill_only_missing and a_exists)
```

Call `render_practice_pdf` only if `not skip_q`. Call `render_answer_pdf` only if `om == "questions_and_answers" and not skip_a`. Append Artifact rows only for kinds that were actually written.

If both files are present, `fill_only_missing` is false, so both are rewritten — same as today's 「按此考点再生成」.

In `run_knowledge_analysis`, after writing the Markdown (keep today's write) and `session.add(p)`:

```python
        p.knowledge_explanation_hidden = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py tests/test_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/test_artifact_delete.py
git commit -m "feat: regenerate only the deleted practice PDF"
```

### Task 5: 「生成文件」每一条旁边删除

**Files:**
- Modify: `frontend/src/components/ArtifactCenter.tsx`
- Modify: `frontend/src/components/Chat.tsx`

There are no frontend unit tests in this repo. Backend tests already cover delete. Do not add a Jest harness.

- [ ] **Step 1: Add delete on each item**

In `ArtifactCenter`, add `onDeleteArtifact: (art: StreamArtifact) => void`. Next to the regenerate button (every item with an `id`, including `md:…` and PDF kinds), a button labeled `删除`. `disabled={busy}`. On click:

```ts
if (!confirm("只删这份文件，题目和考点还在。确定删除？")) return;
onDeleteArtifact(a);
```

Do not invent a new page. Do not restyle the list beyond this button.

- [ ] **Step 2: Wire Chat.tsx**

```ts
  const handleDeleteArtifact = useCallback(
    async (art: StreamArtifact) => {
      if (!art.id) return;
      const r = await fetch(
        `${API}/api/conversations/${conversationId}/artifacts/${encodeURIComponent(art.id)}`,
        { method: "DELETE" },
      );
      if (!r.ok) {
        alert("删除失败，请稍后重试");
        return;
      }
      const body = await r.json().catch(() => ({ ok: false }));
      if (body.ok === false) {
        alert("删除失败，请稍后重试");
        return;
      }
      await loadThread(conversationId);
    },
    [conversationId, loadThread],
  );
```

Pass `onDeleteArtifact={handleDeleteArtifact}` into `ArtifactCenter`. Do not show stack traces, secrets, or paper text.

- [ ] **Step 3: Run backend tests once more**

Run: `cd backend && python -m pytest tests/test_artifact_delete.py tests/test_api.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ArtifactCenter.tsx frontend/src/components/Chat.tsx
git commit -m "feat: let teachers delete a PDF from generated files"
```

## Spec coverage

- 每条 PDF 旁边删除、不点就是保留：Task 5。
- 练习卷、参考答案、考点说明各删各的：Task 1 与 Task 3。
- 确认文案「只删这份文件，题目和考点还在」：Task 5。
- 删文件和产物记录，题目考点还在：Task 1、Task 3。
- 列表拿掉这一条；缺失文件不展示：Task 2、Task 3。
- 旧 Markdown 不删、不挂回列表：Task 2、Task 3。
- 再生成只补被删的那一份；分析成功后考点说明回来：Task 4。
- 文件已不在仍去掉记录；失败短中文、不露堆栈：Task 2、Task 3、Task 5。
- 整段删对话不改：计划没有改 `conversation_delete.py`。
