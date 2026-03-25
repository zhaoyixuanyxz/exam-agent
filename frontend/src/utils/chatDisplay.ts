/**
 * 聊天界面展示用：去掉练习题等 JSON，不影响接口与后端落库（仅前端显示层）。
 * PracticeSet 的 stem/answer_outline 里常有 LaTeX（含 { }），必须用「字符串感知」的括号匹配。
 */

function removeCompleteJsonFences(s: string): string {
  return s.replace(/```json\s*[\s\S]*?```/gi, "");
}

/** 任意语言标记的 fenced 块，内容为 PracticeSet 形 JSON 时整段去掉（模型有时不写 json 标签）。 */
function removeFencedPracticeBlocks(s: string): string {
  return s.replace(/```\w*\s*([\s\S]*?)```/g, (full, inner: string) => {
    const t = inner.trim();
    if (
      t.startsWith("{") &&
      t.includes('"questions"') &&
      (t.includes('"knowledge_point_key"') || t.includes('"knowledge_point_name"')) &&
      t.length > 120
    ) {
      return "";
    }
    return full;
  });
}

/** 最后一个 ```json 若未出现闭合 ```，则从该处截断（流式输出时常态）。 */
function truncateUnclosedJsonFence(s: string): string {
  const re = /```json\s*/gi;
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
  if (
    !after.includes('"questions"') ||
    (!after.includes('"knowledge_point_key"') && !after.includes('"knowledge_point_name"'))
  ) {
    return s;
  }
  return s.slice(0, lastOpen).replace(/\s+$/u, "");
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

function looksLikePracticeSetBlob(blob: string): boolean {
  if (blob.length < 120 || !blob.includes('"questions"')) return false;
  if (
    !blob.includes('"knowledge_point_key"') &&
    !blob.includes('"knowledge_point_name"')
  ) {
    return false;
  }
  return true;
}

/** 去掉裸露的 PracticeSet JSON（支持题面 LaTeX 中的花括号）。 */
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
    if (looksLikePracticeSetBlob(blob)) {
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

/** 流式输出未写完的 PracticeSet：有起始 `{` 但缺少配对的 `}` 时整段尾部不展示。 */
function stripIncompleteTrailingPracticeJson(s: string): string {
  for (let j = s.lastIndexOf("{"); j >= 0; ) {
    const close = findMatchingObjectBrace(s, j);
    if (close === -1) {
      const tail = s.slice(j);
      if (
        tail.includes('"questions"') &&
        (tail.includes('"knowledge_point_key"') ||
          tail.includes('"knowledge_point_name"')) &&
        tail.length > 80
      ) {
        return s.slice(0, j).replace(/\s+$/u, "");
      }
    }
    j = s.lastIndexOf("{", j - 1);
  }
  return s;
}

export function textForChatDisplay(raw: string): string {
  if (!raw) return "";
  let s = removeCompleteJsonFences(raw);
  s = removeFencedPracticeBlocks(s);
  s = truncateUnclosedJsonFence(s);
  s = truncateUnclosedGenericPracticeFence(s);
  s = removeCompleteJsonFences(s);
  s = removeFencedPracticeBlocks(s);
  s = stripAllBarePracticeJson(s);
  s = stripIncompleteTrailingPracticeJson(s);
  return s.replace(/\n{3,}/g, "\n\n").trim();
}
