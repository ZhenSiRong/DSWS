import type { ReactNode } from "react";

import type { StepDef, StepVisualStatus, StepState } from "../types";

interface Props {
  steps: StepDef[];
  states: Record<string, StepState>;
}

const STATUS_TEXT: Record<StepVisualStatus, string> = {
  pending: "等待",
  running: "执行中",
  success: "完成",
  error: "失败",
  skipped: "未触发",
  cancelled: "已取消",
};

function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs === null || durationMs === undefined) return "";
  if (durationMs < 1000) return `${Math.round(durationMs)} ms`;
  return `${(durationMs / 1000).toFixed(2)} s`;
}

/* 每种状态一套工具类；`.rail-*` 类名保留给连接线与 UI 测试使用。 */
const MARKER_CLASS: Record<StepVisualStatus, string> = {
  pending: "border-line bg-panel text-muted",
  running: "border-brass bg-brass-soft text-brass",
  success: "border-moss-line bg-moss-soft font-bold text-moss",
  error: "border-tomato-line bg-tomato-soft font-bold text-tomato",
  skipped: "border-dashed border-line bg-panel text-faint",
  cancelled: "border-dashed border-faint bg-panel font-bold text-cancelled-ink",
};

const LABEL_CLASS: Record<StepVisualStatus, string> = {
  pending: "",
  running: "font-semibold",
  success: "",
  error: "",
  skipped: "text-muted",
  cancelled: "text-muted",
};

const STATUS_CLASS: Record<StepVisualStatus, string> = {
  pending: "text-muted",
  running: "text-muted",
  success: "text-moss",
  error: "text-tomato",
  skipped: "italic text-faint",
  cancelled: "italic text-cancelled-ink",
};

/**
 * 竖向导轨。
 *
 * 旧版是 820×780 的绝对定位画布：窗口一小就裁切，步骤一多就要重算坐标。
 * 新版用普通文档流：天然响应式，新增步骤不需要改任何坐标。
 *
 * S6 起多了一个「已取消」态：取消不是失败，也不是完成——它有自己的样子。
 */
export default function StepRail({ steps, states }: Props) {
  return (
    <ol
      className="rail m-0 list-none px-5 pb-5 pt-4"
      aria-label="执行步骤"
    >
      {steps.map((step, index) => {
        const state = states[step.id];
        const status: StepVisualStatus = state?.status ?? "pending";

        let marker: ReactNode;
        switch (status) {
          case "success":
            marker = "✓";
            break;
          case "error":
            marker = "×";
            break;
          case "running":
            marker = (
              <span className="spinner inline-block size-3.5 animate-spinner rounded-full border-2 border-current border-r-transparent" />
            );
            break;
          case "skipped":
            marker = "–";
            break;
          case "cancelled":
            marker = "⊘";
            break;
          default:
            marker = index + 1;
        }

        return (
          <li
            key={step.id}
            className={`rail-item rail-${status} relative grid grid-cols-[32px_minmax(0,1fr)] gap-3 py-2`}
          >
            <div
              className={`rail-marker relative z-[1] grid size-8 place-items-center rounded-full border-[1.5px] text-[13px] tabular-nums ${MARKER_CLASS[status]}`}
              aria-hidden="true"
            >
              {marker}
            </div>

            <div className="rail-body flex min-h-8 items-center justify-between gap-2.5">
              <span className={`rail-label text-sm ${LABEL_CLASS[status]}`}>
                {step.label}
              </span>
              <span className="rail-meta flex items-baseline gap-2 whitespace-nowrap">
                <span
                  className={`rail-status text-[11px] ${STATUS_CLASS[status]}`}
                >
                  {STATUS_TEXT[status]}
                </span>
                {status === "success" && state?.duration_ms != null && (
                  <span className="rail-duration font-mono text-[11px] text-moss">
                    {formatDuration(state.duration_ms)}
                  </span>
                )}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
