import { useState } from "react";

interface Props {
  disabled: boolean;
  onSubmit: (query: string) => void;
  /** 运行中时显示「停止」。取消是独立状态，不是完成。 */
  onStop?: () => void;
  running?: boolean;
}

export default function Composer({
  disabled,
  onSubmit,
  onStop,
  running = false,
}: Props) {
  const [value, setValue] = useState("");

  function submit() {
    const query = value.trim();
    if (!query || disabled) return;
    onSubmit(query);
    setValue("");
  }

  return (
    <form
      className="composer flex items-end gap-2.5 px-5 pb-5 pt-3.5"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        className="min-h-14 max-h-40 flex-1 resize-y rounded-field border border-line bg-field px-3.5 py-3 font-sans text-sm leading-normal text-ink outline-none transition-[border-color,box-shadow] duration-150 focus:border-brass-line focus:shadow-[0_0_0_3px_rgba(168,122,32,0.14)] disabled:bg-field-disabled disabled:text-muted placeholder:text-[#757575]"
        value={value}
        rows={2}
        disabled={disabled}
        aria-label="问题"
        maxLength={500}
        placeholder="问点什么，例如：华北地区销售额是多少？（Enter 发送，Shift+Enter 换行）"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault();
            submit();
          }
        }}
      />
      {running && onStop ? (
        <button
          type="button"
          className="stop-button cursor-pointer rounded-field border border-tomato-line bg-tomato-soft px-5 py-3 text-base font-semibold text-tomato hover:bg-stop-hover"
          onClick={onStop}
        >
          停止
        </button>
      ) : (
        <button
          type="submit"
          className="h-11 cursor-pointer rounded-field border-0 bg-ink px-[22px] text-sm font-semibold text-bubble-ink transition-[transform,opacity] duration-150 hover:enabled:-translate-y-px disabled:cursor-not-allowed disabled:opacity-[0.45]"
          disabled={disabled || !value.trim()}
        >
          {disabled ? "执行中…" : "提问"}
        </button>
      )}
    </form>
  );
}
