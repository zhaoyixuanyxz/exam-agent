import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
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
