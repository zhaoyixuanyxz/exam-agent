from typing import Any, Literal

from pydantic import BaseModel, Field

# 分块练习 PDF 仅使用以下五种题型（与出题提示、解析归一化一致）
PracticeQtype = Literal["单选", "多选", "填空", "简答", "判断"]
PRACTICE_QTYPE_VALUES: tuple[str, ...] = ("单选", "多选", "填空", "简答", "判断")


class ContentBlock(BaseModel):
    type: Literal["text", "image_ref", "table", "math_latex"]
    content: str = ""
    ref: str | None = None


class QuestionItem(BaseModel):
    order_index: int
    qtype: str = Field(description="选择/填空/判断/主观等")
    stem: str
    options: list[str] = Field(default_factory=list)
    blocks: list[ContentBlock] = Field(default_factory=list)


class PaperSection(BaseModel):
    title: str = ""
    questions: list[QuestionItem] = Field(default_factory=list)


class StructuredPaper(BaseModel):
    title: str = ""
    sections: list[PaperSection] = Field(default_factory=list)


class AlignmentMeta(BaseModel):
    grade_min: str = Field(description="初一|初二|...|高三")
    grade_max: str
    subject: Literal["数学", "物理", "化学", "生物"] | str
    type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="如 {'选择题':3,'填空题':2}",
    )


class KnowledgePointItem(BaseModel):
    key: str = Field(description="稳定英文或拼音键，用于文件名")
    name: str
    summary: str = Field(max_length=80, description="考点概述50字以内")
    book_chapter_hint: str = ""


class QuestionKnowledgeMapping(BaseModel):
    question_order: int
    knowledge_point_key: str


class KnowledgeAnalysisResult(BaseModel):
    theme_title: str = Field(description="试题考点集结主题名")
    knowledge_points: list[KnowledgePointItem]
    mappings: list[QuestionKnowledgeMapping]


class PracticeQuestion(BaseModel):
    order_index: int
    qtype: PracticeQtype
    stem: str
    options: list[str] = Field(default_factory=list)
    answer_outline: str = ""


class PracticeSet(BaseModel):
    knowledge_point_key: str
    knowledge_point_name: str
    questions: list[PracticeQuestion] = Field(min_length=1)


class ChatStreamEvent(BaseModel):
    event: Literal["token", "tool", "artifact", "error", "done"]
    data: dict[str, Any] = Field(default_factory=dict)
