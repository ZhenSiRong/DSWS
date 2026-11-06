/**
 * 智能体接口客户端
 * 封装后端 /api/query SSE 流式接口请求与事件解析逻辑
 */
import type { AgentEvent } from "../types/agent";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

// 当前 v2 后端发的是契约里的步骤 id；原版界面按中文节点名点亮流程图。
// 这里做一层纯展示映射，不改 SSE 契约，也不改后端。
const STEP_LABELS: Record<string, string> = {
  extract_keywords: "抽取关键词",
  recall_column: "召回字段信息",
  recall_metric: "召回指标信息",
  recall_value: "召回字段取值",
  merge_retrieved_info: "合并召回信息",
  filter_metric: "过滤指标信息",
  filter_table: "过滤表信息",
  add_extra_context: "添加额外上下文",
  generate_sql: "生成SQL",
  validate_sql: "校验SQL",
  correct_sql: "校正SQL",
  run_sql: "执行SQL",
};

function normalizeStep(step: string) {
  return STEP_LABELS[step] ?? step;
}

/**
 * 当前后端的结果是 `{ columns: [{name,type}], rows: [[...]] }`；
 * 原版结果表按 `Array<Record<string, unknown>>` 渲染。这里转成原版形状。
 */
function normalizeResultData(data: unknown): unknown {
  if (Array.isArray(data)) return data;

  if (data && typeof data === "object") {
    const payload = data as { columns?: unknown; rows?: unknown };
    if (Array.isArray(payload.columns) && Array.isArray(payload.rows)) {
      const names = payload.columns.map((column) => {
        if (typeof column === "string") return column;
        if (column && typeof column === "object" && "name" in column) {
          return String((column as { name: unknown }).name);
        }
        return String(column);
      });

      return payload.rows.map((row) => {
        if (row && typeof row === "object" && !Array.isArray(row)) {
          return row as Record<string, unknown>;
        }
        const values = Array.isArray(row) ? row : [row];
        return Object.fromEntries(
          names.map((name, index) => [name, values[index] ?? null]),
        );
      });
    }
  }

  return data;
}

function normalizeEvent(event: AgentEvent): AgentEvent {
  if (event.type === "progress") {
    return { ...event, step: normalizeStep(event.step) };
  }

  if (event.type === "result") {
    return { ...event, data: normalizeResultData(event.data) };
  }

  if (event.type === "error") {
    const code = (event as { code?: unknown }).code;
    return {
      ...event,
      message: typeof code === "string" && code ? `${event.message}（${code}）` : event.message,
    };
  }

  return event;
}

type QueryOptions = {
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
};

export async function streamQuery(query: string, options: QueryOptions) {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ query }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(`接口请求失败：HTTP ${response.status}`);
  }

  if (!response.body) {
    throw new Error("浏览器未返回可读取的流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split(/\n\n/);
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const event = parseSseChunk(chunk);
      if (event) {
        options.onEvent(event);
      }
    }
  }

  buffer += decoder.decode();
  const tail = parseSseChunk(buffer);
  if (tail) {
    options.onEvent(tail);
  }
}

function parseSseChunk(chunk: string): AgentEvent | null {
  const payload = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n")
    .trim();

  if (!payload) return null;

  try {
    return normalizeEvent(JSON.parse(payload) as AgentEvent);
  } catch {
    return {
      type: "error",
      message: `无法解析后端事件：${payload}`,
    };
  }
}
