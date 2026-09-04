import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)

    papers: Mapped[list["ExamPaper"]] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    attachments_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    raw_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 用户可见名称；缺省时前端可用 id 前 8 位 + 来源类型展示
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # none: 未产出结构化 | pending: 已拆题未确认 | confirmed: 已确认
    structured_confirm_status: Mapped[str] = mapped_column(String(32), default="none")
    structured_version: Mapped[int] = mapped_column(default=0)
    structured_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    structured_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    alignment_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_markdown_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # V2.1：界面「练习生成配置」最后保存的快照；出题工具优先与此合并
    last_practice_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="papers")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="paper")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(String(36), ForeignKey("exam_papers.id"))
    kind: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(1024))
    knowledge_point_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # V2.1：产物元信息（旧行可为空，由列表 API 做兼容兜底）
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    paper: Mapped["ExamPaper"] = relationship(back_populates="artifacts")


class AppUser(Base):
    """V2.3：组织与权限基础（单用户部署时插入默认用户）。"""

    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(256), default="")
    role: Mapped[str] = mapped_column(String(32), default="teacher")
    data_scope_default: Mapped[str] = mapped_column(String(32), default="own")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgePointCanonical(Base):
    """标准考点主数据。"""

    __tablename__ = "knowledge_point_canonicals"
    __table_args__ = (UniqueConstraint("standard_key", name="uq_kp_canonical_standard_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    standard_key: Mapped[str] = mapped_column(String(256), index=True)
    name: Mapped[str] = mapped_column(String(512), default="")
    aliases_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chapter_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    grade_min: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade_max: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeKeyMapping(Base):
    """原始 LLM key -> 标准考点。"""

    __tablename__ = "knowledge_key_mappings"
    __table_args__ = (UniqueConstraint("raw_key", name="uq_knowledge_raw_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    raw_key: Mapped[str] = mapped_column(String(256), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_point_canonicals.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuestionAsset(Base):
    """V2.2：结构化确认后的题目行级资产（可追溯，多版本按 structured_version 区分）。"""

    __tablename__ = "question_assets"
    __table_args__ = (
        UniqueConstraint(
            "paper_id",
            "structured_version",
            "question_order",
            name="uq_question_asset_paper_ver_order",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), index=True)
    paper_id: Mapped[str] = mapped_column(String(36), ForeignKey("exam_papers.id"), index=True)
    structured_version: Mapped[int] = mapped_column(default=0)
    question_order: Mapped[int] = mapped_column()
    section_title: Mapped[str] = mapped_column(String(512), default="")
    qtype: Mapped[str] = mapped_column(String(128), default="")
    stem: Mapped[str] = mapped_column(Text, default="")
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    knowledge_point_keys_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    alignment_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    textbook_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    chapter_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    grade_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subject_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_paper_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="pending")
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("app_users.id"), nullable=True, index=True
    )
    visibility: Mapped[str] = mapped_column(String(32), default="own")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QuestionKnowledgeLink(Base):
    """题目与标准考点关联。"""

    __tablename__ = "question_knowledge_links"
    __table_args__ = (
        UniqueConstraint(
            "question_asset_id",
            "knowledge_point_id",
            name="uq_qkl_qa_kp",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("question_assets.id"), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_point_canonicals.id"), index=True
    )
    raw_key: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaperSet(Base):
    """题单 / 组卷篮。"""

    __tablename__ = "paper_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), index=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("app_users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), default="题单")
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["PaperSetItem"]] = relationship(
        back_populates="paper_set", cascade="all, delete-orphan"
    )


class PaperSetItem(Base):
    __tablename__ = "paper_set_items"
    __table_args__ = (
        UniqueConstraint("paper_set_id", "question_asset_id", name="uq_paper_set_qa"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    paper_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_sets.id"), index=True)
    question_asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("question_assets.id"), index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    paper_set: Mapped["PaperSet"] = relationship(back_populates="items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
