"""Read visible text from one page image via DeepSeek. Tests inject a fake."""

from __future__ import annotations

import base64

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings


def read_image_text(data: bytes) -> str:
    key = settings.require_deepseek_api_key()
    b64 = base64.b64encode(data).decode("ascii")
    llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=key,
        base_url=settings.deepseek_base_url,
        temperature=0,
    )
    msg = llm.invoke(
        [
            SystemMessage(
                content="你是试卷识读助手。只输出这一页上可见的文字，不要解释、不要JSON。"
                "若完全没有可识文字，输出空字符串。"
            ),
            HumanMessage(
                content=[
                    {"type": "text", "text": "请输出这一页试卷上的文字。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ]
            ),
        ]
    )
    c = getattr(msg, "content", "")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(c).strip()
