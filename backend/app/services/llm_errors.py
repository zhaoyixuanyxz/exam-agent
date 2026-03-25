"""Map LLM client errors to user-facing hints (no secrets)."""


def user_message_for_llm_error(exc: BaseException) -> str:
    raw = str(exc)
    low = raw.lower()
    if "deepseek_api_key_missing" in low:
        return (
            "未配置 DeepSeek API 密钥。请在 backend 目录的 .env 中设置 DEEPSEEK_API_KEY="
            "（以 sk- 开头的密钥），保存后重启后端。获取密钥：https://platform.deepseek.com"
        )
    if "deepseek_api_key_placeholder" in low:
        return (
            "DEEPSEEK_API_KEY 为占位符或无效示例值。请改为平台真实密钥（sk- 开头）。"
            "若已在 .env 填写仍如此，请检查 Windows「系统环境变量」里是否设置了错误的 "
            "DEEPSEEK_API_KEY / OPENAI_API_KEY（会覆盖 .env），删除或改正后重启电脑或终端。"
        )
    if (
        "401" in raw
        or "authentication" in low
        or "authentication_error" in low
        or "invalid_request_error" in low
        or "api key" in low
        or "invalid api" in low
    ):
        return (
            "DeepSeek 鉴权失败（401）。请检查 backend\\.env 里的 DEEPSEEK_API_KEY："
            "须为平台发放的以 sk- 开头的有效密钥，无空格、无引号；勿使用占位符。"
            "修改后请重启 uvicorn。"
        )
    return raw


def humanize_known_llm_message(msg: str) -> str | None:
    """If msg matches a known vendor error, return short Chinese; else None."""
    low = msg.lower()
    if "response_format" in low and "unavailable" in low:
        return (
            "出题平台暂时不支持一种自动格式，我们已改成普通对话方式拆题。"
            "请**再发一条消息**试试（例如说「请重新结构化试卷」）；若仍失败，可把试卷**分段粘贴**或重新上传。"
        )
    if "json_schema" in low and ("not" in low or "unsupported" in low or "unavailable" in low):
        return (
            "当前接口不支持自动 JSON 格式约束，系统已改用兼容方式。"
            "请重试结构化；若多次失败，请缩短一次粘贴的文本长度。"
        )
    return None


def tool_error_user_text(prefix: str, exc: BaseException) -> str:
    """prefix e.g. '考点分析失败：' — append Chinese help or technical tail."""
    detail = str(exc)
    friendly = humanize_known_llm_message(detail)
    if friendly:
        return f"{prefix}{friendly}"
    low = detail.lower()
    if (
        "练习题 json" in detail
        or "校验未通过" in detail
        or "未在模型输出中找到可识别的练习题 json" in low
        or "practiceset" in low
    ):
        return (
            f"{prefix}"
            "模型输出过长被截断、或 LaTeX 公式导致 JSON 不完整时容易失败；系统已自动做转义修复与分批出题。"
            "请**再试一次**；若仍失败可先说「该考点先出 6 道题」或换考点。连续失败时可**新开对话**。"
        )
    return f"{prefix}请稍后重试。若反复出现可把内容缩短后重试。技术说明：{detail}"
