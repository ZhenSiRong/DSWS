import { useEffect, useMemo, useRef, useState } from "react";

import Composer from "./components/Composer";
import ErrorCard from "./components/ErrorCard";
import PseudoErrorCard from "./components/PseudoErrorCard";
import ResultTable from "./components/ResultTable";
import StepRail from "./components/StepRail";
import {
  fetchErrorCodes,
  fetchSteps,
  streamQuery,
  cancelQuery,
  ApiError,
  isAbortError,
} from "./lib/api";
import { looksLikePseudoError } from "./lib/result";
import type {
  AgentEvent,
  ErrorCodeSpec,
  ErrorEvent,
  ResultData,
  RunStatus,
  StepDef,
  StepState,
} from "./types";

/**
 * 把「正在跑」的步骤标成失败或取消。
 *
 * 旧系统只有一种：`markRunningAsError` —— 不管出了什么事，统统标成红色
 * 的「失败」。取消不是失败，空结果也不是失败，所以这里分开处理。
 */
function markRunning(
  states: Record<string, StepState>,
  status: "error" | "cancelled",
  step?: string | null,
): Record<string, StepState> {
  const next = { ...states };
  for (const [id, state] of Object.entries(next)) {
    if (state.status === "running") {
      next[id] = { status, duration_ms: null };
    }
  }
  if (step) {
    next[step] = { status, duration_ms: null };
  }
  return next;
}

const RUN_STATUS_TEXT: Record<RunStatus, string> = {
  idle: "待命",
  running: "执行中",
  done: "已完成",
  error: "失败",
  empty: "无数据",
  cancelled: "已取消",
};

export default function App() {
  const [steps, setSteps] = useState<StepDef[]>([]);
  const [states, setStates] = useState<Record<string, StepState>>({});
  const [result, setResult] = useState<ResultData | null>(null);
  const [error, setError] = useState<ErrorEvent | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [lastQuery, setLastQuery] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [errorSpecs, setErrorSpecs] = useState<
    Record<string, ErrorCodeSpec>
  >({});
  const [unknownTypes, setUnknownTypes] = useState<string[]>([]);

  const controllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef<string | null>(null);

  useEffect(() => {
    fetchSteps()
      .then((payload) => setSteps(payload.steps))
      .catch((reason: unknown) =>
        setLoadError(reason instanceof Error ? reason.message : String(reason)),
      );
  }, []);

  useEffect(() => {
    // 错误码表是契约的一部分：前端不硬编码码的含义。
    fetchErrorCodes()
      .then((payload) => {
        const table: Record<string, ErrorCodeSpec> = {};
        for (const spec of payload.codes) table[spec.code] = spec;
        setErrorSpecs(table);
      })
      .catch(() => {
        // 拿不到就退回用码本身当标题——不能因为它把整个界面卡住。
      });
  }, []);

  const conditionalCount = useMemo(
    () => steps.filter((step) => step.conditional).length,
    [steps],
  );

  const runningStep = useMemo(() => {
    const entry = Object.entries(states).find(
      ([, state]) => state.status === "running",
    );
    if (!entry) return null;
    return steps.find((step) => step.id === entry[0]) ?? null;
  }, [states, steps]);

  const stepLabel = useMemo(() => {
    const table: Record<string, string> = {};
    for (const step of steps) table[step.id] = step.label;
    return table;
  }, [steps]);

  async function ask(query: string) {
    const controller = new AbortController();
    controllerRef.current = controller;
    requestIdRef.current = null;

    setStatus("running");
    setStates({});
    setResult(null);
    setError(null);
    setUnknownTypes([]);
    setLastQuery(query);

    let terminal = false;

    try {
      await streamQuery(
        query,
        (event: AgentEvent) => {
          if (terminal) return;

          // 用 switch，不用「progress / result / 其余全当 error」。
          //
          // 旧系统的兜底分支把**任何**未知事件类型都当成失败：后端将来
          // 加一个 `type:"meta"`，用户就会看到一次莫名的失败，而红框还
          // 不显示（message 是 undefined）。契约长了一条腿，不该变成报错。
          switch (event.type) {
            case "progress": {
              if (!steps.some((step) => step.id === event.step)) {
                throw new ApiError("UNKNOWN_STEP", `未知步骤：${event.step}`);
              }
              setStates((previous) => ({
                ...previous,
                [event.step]: {
                  status: event.status,
                  duration_ms: event.duration_ms,
                },
              }));
              return;
            }

            case "result": {
              terminal = true;
              setResult(event.data);
              setStatus("done");
              return;
            }

            case "error": {
              // error 事件：三种类别三种处理。
              terminal = true;
              setError(event);
              if (event.class === "empty") {
                // 合法但没有数据：不算失败，步骤也不标红。
                setStatus("empty");
                return;
              }
              if (event.class === "cancelled") {
                setStatus("cancelled");
                setStates((previous) => markRunning(previous, "cancelled"));
                return;
              }
              setStatus("error");
              setStates((previous) => markRunning(previous, "error", event.step));
              return;
            }
          }
        },
        {
          signal: controller.signal,
          onRequestId: (requestId) => {
            requestIdRef.current = requestId;
          },
          onUnknownType: (type) => {
            // 后端加了新事件类型：记一笔，继续跑。
            console.warn(`[契约] 收到未知事件类型：${type}（已忽略）`);
            setUnknownTypes((previous) =>
              previous.includes(type) ? previous : [...previous, type],
            );
          },
        },
      );

      // 契约要求：流必须以 result 或 error 收尾。
      // 静默结束 = 失败，不能当成成功（旧系统的缺陷之一）。
      if (!terminal) {
        setError({
          type: "error",
          code: "STREAM_INCOMPLETE",
          class: "failure",
          message: "连接已结束，但没有收到结果或错误事件。",
          step: null,
        });
        setStatus("error");
        setStates((previous) => markRunning(previous, "error"));
      }
    } catch (reason: unknown) {
      if (isAbortError(reason)) {
        // 用户点了停止：状态是「已取消」，**不是** done。
        setStatus("cancelled");
        setStates((previous) => markRunning(previous, "cancelled"));
        return;
      }
      setError({
        type: "error",
        code: reason instanceof ApiError ? reason.code : "NETWORK_ERROR",
        class: "failure",
        message: reason instanceof Error ? reason.message : String(reason),
        step: null,
      });
      setStatus("error");
      setStates((previous) => markRunning(previous, "error"));
    } finally {
      controllerRef.current = null;
    }
  }

  /**
   * 停止一次问数。
   *
   * 两件事同时做：告诉服务端别跑了（`/api/cancel`），并把本地这条流
   * 掐断（AbortController）。界面状态是「已取消」——旧系统这里写的是
   * `status: isAbort ? "done" : "error"`，取消被算成了完成。
   */
  function stop() {
    const requestId = requestIdRef.current;
    if (requestId) {
      void cancelQuery(requestId).catch(() => {
        // 服务端已经结束就算了：本地状态照样是「已取消」。
      });
    }
    controllerRef.current?.abort();
    setStatus("cancelled");
    setStates((previous) => markRunning(previous, "cancelled"));
  }

  // 「伪 SQL 当数据行」：后端把失败编成了一行数据。
  // 止损——不把它画成一张成功的表。
  const pseudoError = result ? looksLikePseudoError(result) : null;

  return (
    <div className="app mx-auto max-w-[1180px] px-6 pb-7 pt-[34px] max-[900px]:px-4 max-[900px]:py-6">
      <header className="masthead mb-[22px] flex items-end justify-between gap-5 max-[900px]:flex-col max-[900px]:items-start">
        <div>
          <p className="eyebrow mb-1.5 mt-0 text-xs uppercase tracking-[0.18em] text-brass">
            从零重建 · 教学版
          </p>
          <h1 className="m-0 font-serif text-[clamp(30px,4vw,44px)] font-semibold tracking-[0.02em]">
            电商问数智能体
          </h1>
          <p className="subtitle mb-0 mt-2 text-sm text-muted">
            契约先行：类型从契约生成 · 步骤目录唯一源 · 每一种失败都有名字
          </p>
        </div>
        <div className="badges flex flex-wrap justify-end gap-2 max-[900px]:justify-start">
          <span className="badge badge-stage whitespace-nowrap rounded-full border border-brass-line bg-brass-soft px-[11px] py-1.5 text-xs font-semibold text-brass-deep">
            S7 契约驱动前端
          </span>
          <span className="badge whitespace-nowrap rounded-full border border-line bg-panel/70 px-[11px] py-1.5 text-xs text-muted">
            {steps.length} 步
          </span>
          <span className="badge whitespace-nowrap rounded-full border border-line bg-panel/70 px-[11px] py-1.5 text-xs text-muted">
            {conditionalCount} 条件步
          </span>
          <span
            className="badge whitespace-nowrap rounded-full border border-line bg-panel/70 px-[11px] py-1.5 text-xs text-muted"
            data-testid="run-status"
          >
            {RUN_STATUS_TEXT[status]}
          </span>
        </div>
      </header>

      {loadError && (
        <div className="rounded-xl border border-tomato-line border-l-4 border-l-tomato bg-tomato-soft px-4 py-3.5 text-[13px] leading-[1.6] text-error-ink">
          <strong>步骤目录加载失败</strong>
          <p className="mb-0 mt-1.5">{loadError}</p>
          <p className="hint mb-0 mt-1.5 text-[12px] text-error-hint">
            请确认后端已在 8100 端口启动。
          </p>
        </div>
      )}

      {unknownTypes.length > 0 && (
        <p
          className="notice mb-3.5 mt-0 rounded-[10px] border border-brass-line bg-brass-soft px-3 py-2.5 text-xs leading-[1.6] text-brass-deep"
          data-testid="unknown-type-notice"
        >
          收到契约之外的事件类型（{unknownTypes.join("、")}），已忽略。
          前端不需要升级也能继续用——这是「契约长了一条腿」的正确反应。
        </p>
      )}

      <main className="layout grid grid-cols-[330px_minmax(0,1fr)] items-start gap-[18px] max-[900px]:grid-cols-1">
        <aside className="panel rail-panel rounded-panel border border-line bg-panel shadow-panel">
          <div className="panel-head flex items-baseline justify-between gap-3 px-5 pt-[18px]">
            <h2 className="m-0 text-[15px] font-bold tracking-[0.08em]">执行链路</h2>
            <span className="panel-note text-right text-xs text-muted">来自 /api/steps</span>
          </div>
          <StepRail steps={steps} states={states} />
        </aside>

        <section className="panel chat-panel flex min-h-[620px] flex-col rounded-panel border border-line bg-panel shadow-panel max-[900px]:min-h-[520px]">
          <div className="panel-head flex items-baseline justify-between gap-3 px-5 pt-[18px]">
            <h2 className="m-0 text-[15px] font-bold tracking-[0.08em]">问数</h2>
            <span className="panel-note text-right text-xs text-muted">
              {status === "running" && runningStep
                ? `正在执行：${runningStep.label}`
                : RUN_STATUS_TEXT[status]}
            </span>
          </div>

          <div className="chat-body flex flex-1 flex-col gap-4 px-5 pb-2 pt-[18px]">
            {!lastQuery && (
              <div className="empty-state my-2 rounded-card border border-dashed border-dash p-5 text-sm leading-[1.7] text-muted">
                <p className="empty-title mb-2.5 mt-0 text-base font-semibold leading-[1.7] text-ink">
                  类型从契约生成，不从记忆硬编码。
                </p>
                <p className="mb-2.5 mt-0">
                  事件的每一个字段都来自
                  <strong>contracts/sse.schema.json</strong>：
                  <strong>改了契约，重新生成，界面跟着变。</strong>
                </p>
                <ul className="m-0 list-disc pl-[18px]">
                  <li className="my-1">步骤列表由后端下发，前端零硬编码</li>
                  <li className="my-1">
                    每条事件都通过契约校验，未知类型被忽略而不是当成失败
                  </li>
                  <li className="my-1">数字就是数字：Decimal 不再变成字符串</li>
                </ul>
              </div>
            )}

            {lastQuery && (
              <div className="query-bubble max-w-[82%] self-end rounded-[14px_14px_4px_14px] bg-ink px-4 py-3 text-sm leading-[1.6] text-bubble-ink">
                {lastQuery}
              </div>
            )}

            {status === "running" && (
              <div className="running-hint flex items-center gap-2 text-[13px] text-brass">
                <span className="spinner dark inline-block size-3.5 animate-spinner rounded-full border-2 border-current border-r-transparent" />
                正在执行…
              </div>
            )}

            {result && pseudoError && (
              <PseudoErrorCard
                text={pseudoError}
                column={result.columns[0]?.name ?? ""}
              />
            )}

            {result && !pseudoError && <ResultTable data={result} />}

            {error && (
              <ErrorCard
                error={error}
                spec={errorSpecs[error.code]}
                stepLabel={error.step ? (stepLabel[error.step] ?? null) : null}
              />
            )}
          </div>

          <Composer
            disabled={status === "running" || steps.length === 0}
            running={status === "running"}
            onStop={stop}
            onSubmit={ask}
          />
        </section>
      </main>

      <footer className="footer mt-[22px] flex flex-wrap justify-between gap-2 border-t border-line/80 pt-3.5 text-xs text-footer">
        <span>rebuild/ · S7</span>
        <span>下一步 S8：性能基线与 P50/P95 预算</span>
      </footer>
    </div>
  );
}
