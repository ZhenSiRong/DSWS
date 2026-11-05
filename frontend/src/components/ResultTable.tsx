import { useMemo, useState } from "react";

import {
  buildCopyPayload,
  describeColumns,
  isNumericString,
} from "../lib/result";
import type { CellValue, ResultData } from "../types";

interface Props {
  data: ResultData;
}

const NUMBER_FORMAT = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
});

/**
 * 单元格怎么显示。
 *
 * 关键在**不靠猜**：列类型由契约声明（`result.data.columns[].type`），
 * 前端照着它渲染。旧系统一律 `String(value)`，于是数字和字符串在屏幕
 * 上长得一模一样，复制出去才发现一个是 `"10"`、一个是 `10`。
 */
function formatCell(value: CellValue, type: string): string {
  if (value === null) return "NULL";
  if (type === "number" && typeof value === "number") {
    return NUMBER_FORMAT.format(value);
  }
  if (type === "boolean" && typeof value === "boolean") {
    return value ? "是" : "否";
  }
  return String(value);
}

/**
 * 结果表格。
 *
 * 逐条对上审计里的前端缺陷：
 *
 *   F4  rows 为空      → 显式空态块（而不是整张表消失）
 *   F6  整列都是 NULL  → 列头标「无数据」+ 顶部一条说明
 *   F10 数字不格式化  → 千分位；字符串形式的数字单独标注
 *   F13 复制丢类型    → 复制的是 **JSON**（列类型 + 原始值），数字就是数字
 */
export default function ResultTable({ data }: Props) {
  const [copied, setCopied] = useState(false);
  const columns = useMemo(() => describeColumns(data), [data]);
  const emptyColumns = columns.filter((column) => column.allNull);

  async function copy() {
    const payload = buildCopyPayload(data);
    try {
      await navigator.clipboard.writeText(payload);
    } catch {
      legacyCopy(payload);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  if (data.rows.length === 0) {
    return (
      <div
        className="result-empty flex flex-col gap-1.5 rounded-card border border-dashed border-dash bg-empty-bg p-[18px] text-[13px] text-muted"
        data-testid="result-empty"
      >
        <strong className="text-ink">查询成功，但没有数据。</strong>
        <span>这通常意味着筛选条件超出了数据范围，而不是系统故障。</span>
      </div>
    );
  }

  return (
    <div className="result-block flex flex-col gap-2.5">
      {emptyColumns.length > 0 && (
        <p
          className="result-note m-0 rounded-[10px] border border-dashed border-dash bg-empty-bg px-3 py-2.5 text-xs leading-[1.6] text-note"
          data-testid="null-columns-note"
        >
          有 {emptyColumns.length} 列没有取到数据（
          {emptyColumns.map((column) => column.name).join("、")}
          ）——这些列全是 NULL，不是 0。
        </p>
      )}

      <div className="table-wrap overflow-x-auto rounded-card border border-line">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.name}
                  className={[
                    "whitespace-nowrap border-b border-line bg-th-bg px-3.5 py-[11px] text-xs font-semibold tracking-[0.05em]",
                    column.type === "number" ? "text-right" : "text-left",
                    column.allNull ? "text-faint" : "text-th-ink",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {column.name}
                  <span className="col-type ml-1.5 font-mono text-[10px] font-normal text-type">
                    {column.type}
                  </span>
                  {column.allNull && (
                    <span
                      className="col-flag ml-1.5 rounded-full border border-current px-1.5 py-px text-[10px] font-normal tracking-normal opacity-75"
                      data-testid="col-all-null"
                    >
                      无数据
                    </span>
                  )}
                  {column.typeMismatch && (
                    <span
                      className="col-flag col-flag--warn ml-1.5 rounded-full border border-current px-1.5 py-px text-[10px] font-normal tracking-normal text-tomato opacity-100"
                      title="契约说这一列是数字，实际收到的是字符串"
                    >
                      类型不符
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="[&:last-child>td]:border-b-0">
                {columns.map((column, columnIndex) => {
                  const value = row[columnIndex] ?? null;
                  const numericString = isNumericString(value);
                  return (
                    <td
                      key={column.name}
                      data-testid={
                        numericString ? "cell-numeric-string" : undefined
                      }
                      title={
                        numericString
                          ? "这是字符串形式的数字：复制出去仍然是字符串"
                          : undefined
                      }
                      className={[
                        "border-b border-row-line px-3.5 py-2.5 tabular-nums",
                        column.type === "number" ? "text-right" : "",
                        value === null
                          ? "cell-null font-mono text-xs italic text-faint"
                          : "",
                        numericString
                          ? "cell-numeric-string font-mono underline decoration-dotted underline-offset-[3px]"
                          : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {formatCell(value, column.type)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="result-actions flex flex-wrap items-center gap-2.5 text-muted">
        <button
          type="button"
          className="ghost-button cursor-pointer rounded-lg border border-current bg-transparent px-3 py-[5px] text-xs text-current opacity-80 hover:opacity-100"
          onClick={copy}
        >
          {copied ? "已复制 ✓" : "复制结果（JSON）"}
        </button>
        <span className="result-hint text-[11px] opacity-80">
          复制的是 JSON：数字就是数字，字符串就是字符串。
        </span>
      </div>
    </div>
  );
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
    // 复制不了就算了：数据在页面上看得见
  }
  document.body.removeChild(area);
}
