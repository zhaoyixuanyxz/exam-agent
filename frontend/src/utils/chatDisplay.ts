/**
 * 聊天界面展示用：去掉练习题等 JSON，不影响接口与后端落库（仅前端显示层）。
 * PracticeSet 的 stem 里常有 LaTeX 与未转义引号，会搞乱括号扫描；因此除「字符串感知」括号匹配外，
 * 还以 "questions" 为锚点做多层回退剥离。
 */

function removeCompleteJsonFences(s: string): string {
  return s.replace(/```(?:json|JSON)?\s*[\s\S]*?```/gi, "");
}

/** 与 JSON 字符串规则一致：双引号内忽略 { }，处理 \\ 与 \". */
function findMatchingObjectBrace(s: string, openIdx: number): number {
  if (s[openIdx] !== "{") return -1;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = openIdx; i < s.length; i++) {
    const c = s[i];
    if (esc) {
      esc = false;
      continue;
    }
    if (inStr) {
      if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') {
      inStr = true;
      continue;
    }
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

/** 是否为分块练习 / PracticeSet 形 JSON（放宽条件，减少漏网）。 */
function looksLikePracticePayload(blob: string): boolean {
  if (blob.length < 72) return false;
  const hasQuestions = blob.includes('"questions"') || blob.includes("'questions'");
  if (!hasQuestions) return false;
  const hasQuestionShape =
    blob.includes('"stem"') ||
    blob.includes("'stem'") ||
    blob.includes('"qtype"') ||
    blob.includes("'qtype'") ||
    blob.includes("order_index") ||
    blob.includes("answer_outline");
  if (!hasQuestionShape) return false;
  if (blob.includes("knowledge_point") || blob.includes("KnowledgePoint")) return true;
  return blob.length >= 160;
}

function looksLikeIncompletePracticeTail(tail: string): boolean {
  if (tail.length < 120) return false;
  const hasQuestions = tail.includes('"questions"') || tail.includes("'questions'");
  if (!hasQuestions) return false;
  return (
    tail.includes("stem") ||
    tail.includes("qtype") ||
    tail.includes("order_index") ||
    tail.includes("answer_outline")
  );
}

/** 从每个 "questions" 锚点向左尝试多个 `{`，找到第一个括号平衡且像 PracticeSet 的对象整块删除。 */
function stripPracticeObjectsByQuestionsAnchor(s: string): string {
  const markers = ['"questions"', "'questions'"] as const;
  let changed = true;
  while (changed) {
    changed = false;
    outer: for (const qm of markers) {
      let from = 0;
      while (true) {
        const qi = s.indexOf(qm, from);
        if (qi === -1) break;
        let pos = qi - 1;
        while (pos >= 0) {
          const bStart = s.lastIndexOf("{", pos);
          if (bStart === -1) break;
          const close = findMatchingObjectBrace(s, bStart);
          if (close === -1 || close < qi) {
            pos = bStart - 1;
            continue;
          }
          const blob = s.slice(bStart, close + 1);
          if (!blob.includes(qm)) {
            pos = bStart - 1;
            continue;
          }
          if (looksLikePracticePayload(blob)) {
            const left = s.slice(0, bStart).replace(/\s+$/u, "");
            const right = s.slice(close + 1).replace(/^\s+/u, "");
            s = [left, right].filter(Boolean).join("\n\n");
            changed = true;
            break outer;
          }
          pos = bStart - 1;
        }
        from = qi + 1;
      }
    }
  }
  return s;
}

/** 括号无法闭合时（流式或畸形 JSON），从最后一个可疑 `{` 截掉尾部。 */
function stripTrailingUnclosedPracticeByAnchor(s: string): string {
  const markers = ['"questions"', "'questions'"] as const;
  for (const qm of markers) {
    const qi = s.lastIndexOf(qm);
    if (qi === -1) continue;
    let pos = qi - 1;
    while (pos >= 0) {
      const bStart = s.lastIndexOf("{", pos);
      if (bStart === -1) break;
      const close = findMatchingObjectBrace(s, bStart);
      if (close !== -1) {
        pos = bStart - 1;
        continue;
      }
      const tail = s.slice(bStart);
      if (looksLikeIncompletePracticeTail(tail)) {
        return s.slice(0, bStart).replace(/\s+$/u, "");
      }
      pos = bStart - 1;
    }
  }
  return s;
}

/** 任意语言标记的 fenced 块，内容为练习 JSON 时整段去掉。 */
function removeFencedPracticeBlocks(s: string): string {
  return s.replace(/```\w*\s*([\s\S]*?)```/g, (full, inner: string) => {
    const t = inner.trim();
    if (t.startsWith("{") && looksLikePracticePayload(t)) {
      return "";
    }
    if (t.startsWith("{") && t.length >= 72 && t.includes('"questions"') && t.includes("stem")) {
      return "";
    }
    return full;
  });
}

/** 最后一个 ```json 若未出现闭合 ```，则从该处截断。 */
function truncateUnclosedJsonFence(s: string): string {
  const re = /```(?:json|JSON)?\s*/gi;
  let match: RegExpExecArray | null;
  let lastIdx = -1;
  let lastLen = 0;
  while ((match = re.exec(s)) !== null) {
    lastIdx = match.index;
    lastLen = match[0].length;
  }
  if (lastIdx === -1) return s;
  const afterOpen = lastIdx + lastLen;
  if (s.slice(afterOpen).includes("```")) return s;
  return s.slice(0, lastIdx).replace(/\s+$/u, "");
}

/** 未闭合的 ``` + PracticeSet 形 JSON（无 json 标签时）。 */
function truncateUnclosedGenericPracticeFence(s: string): string {
  const re = /```\w*\s*/g;
  let lastOpen = -1;
  let lastLen = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    lastOpen = m.index;
    lastLen = m[0].length;
  }
  if (lastOpen === -1) return s;
  const after = s.slice(lastOpen + lastLen).trimStart();
  if (!after.startsWith("{")) return s;
  if (after.includes("```")) return s;
  if (!looksLikeIncompletePracticeTail(after) && !looksLikePracticePayload(after)) {
    return s;
  }
  return s.slice(0, lastOpen).replace(/\s+$/u, "");
}

function stripBarePracticeJsonOnce(s: string): string {
  let out = "";
  let i = 0;
  while (i < s.length) {
    const open = s.indexOf("{", i);
    if (open === -1) return out + s.slice(i);
    out += s.slice(i, open);
    const close = findMatchingObjectBrace(s, open);
    if (close === -1) return out + s.slice(open);
    const blob = s.slice(open, close + 1);
    if (looksLikePracticePayload(blob)) {
      i = close + 1;
      continue;
    }
    out += blob;
    i = close + 1;
  }
  return out;
}

function stripAllBarePracticeJson(s: string): string {
  let prev = "";
  while (prev !== s) {
    prev = s;
    s = stripBarePracticeJsonOnce(s);
  }
  return s;
}

function stripIncompleteTrailingPracticeJson(s: string): string {
  for (let j = s.lastIndexOf("{"); j >= 0; ) {
    const close = findMatchingObjectBrace(s, j);
    if (close === -1) {
      const tail = s.slice(j);
      if (looksLikeIncompletePracticeTail(tail)) {
        return s.slice(0, j).replace(/\s+$/u, "");
      }
    }
    j = s.lastIndexOf("{", j - 1);
  }
  return s;
}

/** 仍残留大段 JSON 时：去掉从「首个含 questions+stem 的 `{`」到文本末尾（模型常把整坨粘在最后）。 */
function stripTrailingBulkPracticeJson(s: string): string {
  const idx = s.search(/"questions"\s*:\s*\[/);
  if (idx === -1) return s;
  const bStart = s.lastIndexOf("{", idx);
  if (bStart === -1) return s;
  const tail = s.slice(bStart);
  if (tail.length < 400) return s;
  if (
    !tail.includes("stem") &&
    !tail.includes("qtype") &&
    !tail.includes("order_index")
  ) {
    return s;
  }
  const close = findMatchingObjectBrace(s, bStart);
  if (close !== -1) {
    const blob = s.slice(bStart, close + 1);
    if (looksLikePracticePayload(blob)) {
      return s.slice(0, bStart).replace(/\s+$/u, "");
    }
    return s;
  }
  if (looksLikeIncompletePracticeTail(tail)) {
    return s.slice(0, bStart).replace(/\s+$/u, "");
  }
  return s;
}

/** 历史消息：去掉落库时的系统前缀，避免把 thread/paper 上下文展示给用户。 */
export function displayUserMessageContent(raw: string, maxLen = 4000): string {
  if (!raw) return "";
  let s = raw.replace(/^【系统上下文】[\s\S]*?\n\n/u, "").trim();
  if (s.length > maxLen) {
    return `${s.slice(0, maxLen - 1)}…`;
  }
  return s;
}

const PRACTICE_STRIPPED_HINT = "（练习题生成后请在下方「生成文件」中打开 PDF。）";

function appendHintIfStripped(original: string, cleaned: string): string {
  const o = original.trim();
  const c = cleaned.trim();
  if (o.length - c.length < 80) return cleaned;
  if (c.includes("生成文件") || c.includes("PDF")) return cleaned;
  const tail = c.length ? `${c}\n\n${PRACTICE_STRIPPED_HINT}` : PRACTICE_STRIPPED_HINT;
  return tail;
}

export function textForChatDisplay(raw: string): string {
  if (!raw) return "";
  const original = raw;
  let s = removeCompleteJsonFences(raw);
  s = removeFencedPracticeBlocks(s);
  s = truncateUnclosedJsonFence(s);
  s = truncateUnclosedGenericPracticeFence(s);
  s = removeCompleteJsonFences(s);
  s = removeFencedPracticeBlocks(s);
  s = stripAllBarePracticeJson(s);
  s = stripPracticeObjectsByQuestionsAnchor(s);
  s = stripAllBarePracticeJson(s);
  s = stripIncompleteTrailingPracticeJson(s);
  s = stripTrailingUnclosedPracticeByAnchor(s);
  s = stripTrailingBulkPracticeJson(s);
  s = stripPracticeObjectsByQuestionsAnchor(s);
  s = s.replace(/\n{3,}/g, "\n\n").trim();
  return appendHintIfStripped(original, s);
}
