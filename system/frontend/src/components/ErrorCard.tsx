import { useState } from "react";

import type { ErrorClass, ErrorCodeSpec, ErrorEvent } from "../types";

interface Props {
  error: ErrorEvent;
  /** 错误码表里的一项（来自 GET /api/errors）。没有就用码本身当标题。 */
  spec?: ErrorCodeSpec;
  /** 失败步骤的中文名（来自 GET /api/steps）。 */
  stepLabel?: string | null;
}

const CLASS_TEXT: Record<ErrorClass, string> = {
  failure: "失败",
  empty: "无数据",
  cancelled: "已取消",
};

/* class 决定长相：红框 / 虚线空态 / 中性取消卡。 */
const CARD_CLASS: Record<ErrorClass, string> = {
  failure: "border-tomato-line border-l-tomato bg-tomato-soft text-error-ink",
  empty:
    "border-dash border-dashed bg-empty-bg text-ink [border-left:4px_solid_var(--color-brass)]!",
  cancelled: "border-line border-l-faint bg-cancelled-bg text-ink",
};

const CODE_BG: Record<ErrorClass, string> = {
  failure: "bg-[rgba(178,58,42,0.12)]",
  empty: "bg-[rgba(168,122,32,0.14)]",
  cancelled: "bg-[rgba(123,115,102,0.14)]",
};

/**
 * 失败卡片。
 *
 * 三种长相（由 `class` 决定，**不是**由码决定）：
 *
 *   failure    红框 + 红叉 —— 真的失败了
 *   empty      虚线空态卡 —— 查询成功但没有数据，**不标红**
 *   cancelled  中性卡     —— 用户自己停的，不算失败
 *
 * 错误**可复制**：整段文本（码 / 步骤 / 原因码 / 消息 / 原始 SQL）在页面
 * 上看得见，也能一键复制走。旧系统只有一句「查询完成，共 1 行结果。」，
 * 用户拿不走任何东西。
 */
export default function ErrorCard({ error, spec, stepLabel }: Props) {
  const [copied, setCopied] = useState(false);

  const title = spec?.label ?? error.code;
  const detail = error.detail ?? {};
  const text = buildText(error, spec, stepLabel);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // 剪贴板不可用（没有 HTTPS / 没有权限）时退回老办法
      legacyCopy(text);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className={`error-card error-card--${error.class} rounded-xl border border-l-4 px-4 py-3.5 text-[13px] leading-[1.6] ${CARD_CLASS[error.class]}`}
      data-error-code={error.code}
      data-error-class={error.class}
      role="alert"
    >
      <div className="error-head flex items-baseline justify-between gap-3">
        <strong>{title}</strong>
        <code
          className={`whitespace-nowrap rounded-md px-[7px] py-0.5 font-mono text-[11px] ${CODE_BG[error.class]}`}
        >
          {error.code}
        </code>
      </div>

      <p className="error-message mb-0 mt-1.5 whitespace-pre-wrap">
        {error.message}
      </p>

      <p className="error-meta mb-0 mt-1.5 flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-[12px] opacity-[0.85]">
        <span className="error-chip rounded-full border border-current px-2 py-px text-[11px] opacity-75">
          {CLASS_TEXT[error.class]}
        </span>
        {error.step && (
          <span>
            失败步骤：{stepLabel ?? error.step}
          </span>
        )}
        {detail.reason_code && (
          <span>
            原因码：
            <code className="error-reason rounded-md bg-[rgba(127,127,127,0.14)] px-1.5 py-px font-mono text-[11px]">
              {detail.reason_code}
            </code>
          </span>
        )}
        {typeof detail.attempts === "number" && detail.attempts > 0 && (
          <span>已校正 {detail.attempts} 次</span>
        )}
      </p>

      {(detail.original_sql || detail.corrected_sql) && (
        <details className="error-detail mt-2.5 text-[12px]">
          <summary className="cursor-pointer opacity-80">SQL 细节</summary>
          {detail.original_sql && (
            <pre className="mb-0 mt-2 whitespace-pre-wrap break-words rounded-[10px] bg-black/5 px-3 py-2.5 font-mono text-[11px] leading-[1.6]">
              {"原始 SQL\n"}
              {detail.original_sql}
            </pre>
          )}
          {detail.corrected_sql && (
            <pre className="mb-0 mt-2 whitespace-pre-wrap break-words rounded-[10px] bg-black/5 px-3 py-2.5 font-mono text-[11px] leading-[1.6]">
              {"校正后 SQL\n"}
              {detail.corrected_sql}
            </pre>
          )}
        </details>
      )}

      <div className="error-actions mt-3">
        <button
          type="button"
          className="ghost-button cursor-pointer rounded-lg border border-current bg-transparent px-3 py-[5px] text-[12px] text-current opacity-80 hover:opacity-100"
          onClick={copy}
        >
          {copied ? "已复制 ✓" : "复制错误"}
        </button>
      </div>
    </div>
  );
}

function buildText(
  error: ErrorEvent,
  spec?: ErrorCodeSpec,
  stepLabel?: string | null,
): string {
  const detail = error.detail ?? {};
  const lines = [
    `[${error.code}] ${spec?.label ?? ""}`.trim(),
    `类别：${error.class}`,
  ];
  if (error.step) lines.push(`失败步骤：${stepLabel ?? error.step}`);
  if (detail.reason_code) lines.push(`原因码：${detail.reason_code}`);
  lines.push(`消息：${error.message}`);
  if (detail.original_sql) lines.push(`原始 SQL：${detail.original_sql}`);
  if (detail.corrected_sql) lines.push(`校正后 SQL：${detail.corrected_sql}`);
  if (typeof detail.attempts === "number" && detail.attempts > 0) {
    lines.push(`校正次数：${detail.attempts}`);
  }
  if (detail.request_id) lines.push(`request_id：${detail.request_id}`);
  return lines.join("\n");
}

function legacyCopy(text: string): void {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    document.execCommand("copy");
  } catch {
    // 复制不了就算了：文本在页面上看得见
  }
  document.body.removeChild(area);
}
