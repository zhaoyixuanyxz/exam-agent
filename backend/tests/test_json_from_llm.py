from app.models.schemas import StructuredPaper
from app.services.json_from_llm import (
    extract_json_object,
    iter_candidate_dicts_from_llm,
    parse_pydantic_from_llm_text,
    repair_json_latex_escapes_in_strings,
)
from app.services.practice_parse import parse_practice_set_from_llm_text


def test_extract_json_object_raw():
    d = extract_json_object('{"a": 1}')
    assert d == {"a": 1}


def test_extract_json_object_fenced():
    raw = '说明\n```json\n{"title": "t", "sections": []}\n```\n'
    d = extract_json_object(raw)
    assert d["title"] == "t"
    assert d["sections"] == []


def test_parse_pydantic_from_llm_text():
    text = '{"title": "期中", "sections": []}'
    sp = parse_pydantic_from_llm_text(text, StructuredPaper)
    assert sp.title == "期中"
    assert sp.sections == []


def test_extract_json_brace_inside_string():
    raw = '{"title": "括号}测试", "sections": []}'
    d = extract_json_object(raw)
    assert d["title"] == "括号}测试"
    assert d["sections"] == []


def test_parse_pydantic_picks_second_when_first_invalid():
    junk = '{"title": [], "sections": []}'
    good = '{"title": "期中", "sections": []}'
    sp = parse_pydantic_from_llm_text(junk + "\n" + good, StructuredPaper)
    assert sp.title == "期中"


def test_repair_latex_in_json_string_then_parse_practice():
    # 单反斜杠 LaTeX（如 \\angle、\\frac）会破坏 JSON；修复后应能解析
    bad = (
        '{"knowledge_point_key":"k","knowledge_point_name":"几何","questions":['
        '{"order_index":1,"qtype":"简答","stem":"求 \\angle A 与 \\frac{1}{2}","options":[],'
        '"answer_outline":"用相似。"}]}'
    )
    ds = list(iter_candidate_dicts_from_llm(bad))
    assert any("questions" in d for d in ds)
    ps = parse_practice_set_from_llm_text(bad)
    assert ps.questions[0].stem.startswith("求 ")
    assert "\\angle" in ps.questions[0].stem or "angle" in ps.questions[0].stem.lower()


def test_repair_idempotent_on_valid_json():
    ok = '{"a": "\\\\frac{1}{2}"}'
    assert repair_json_latex_escapes_in_strings(ok) == ok
