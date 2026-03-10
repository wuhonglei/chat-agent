import { validateTitle } from "@/utils/header";
import { useClickAway, useMemoizedFn } from "ahooks";
import { App, Input } from "antd";
import classNames from "classnames";
import { useEffect, useRef, useState } from "react";

type Props = {
  title: string;
  className?: string;
  onConfirm: (newTitle: string) => void;
};

export default function HoverButton({ title, onConfirm, className: outerClassName }: Props) {
  const [isEdit, setIsEdit] = useState(false);
  const { message } = App.useApp();
  const [newTitle, setNewTitle] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const resetNewTitle = useMemoizedFn(() => {
    // 异常处理，避免 title 返回过长，导致 input 宽度计算异常
    setNewTitle(title.split("\n")[0].slice(0, 100));
  });

  // 当 title prop 变化时，同步更新 newTitle
  useEffect(() => {
    resetNewTitle();
  }, [resetNewTitle, title]);

  function validateAndConfirm() {
    if (!isEdit) {
      return;
    }

    const trimmedNewTitle = newTitle.trim();
    setIsEdit(false);

    const error = validateTitle(trimmedNewTitle, title);
    if (error) {
      message.warning(error);
      resetNewTitle();
      return;
    }

    onConfirm(trimmedNewTitle);
  }

  useClickAway(() => {
    validateAndConfirm();
  }, containerRef);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTitle(e.target.value);
  };

  const handlePressEnter = () => {
    validateAndConfirm();
  };

  return (
    <div
      ref={containerRef}
      onClick={() => setIsEdit(true)}
      className={classNames(
        "relative h-10 rounded-full px-3 cursor-pointer hover:shadow transition-all duration-300",
        outerClassName
      )}
    >
      {/* 1. 普通模式下用于文本显示; 2. 编辑模式下用于 input 宽度计算 */}
      <div className="leading-10">{newTitle || " "}</div>
      {isEdit && (
        <Input
          autoFocus
          value={newTitle}
          onChange={handleChange}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            borderRadius: "calc(infinity * 1px)",
          }}
          onPressEnter={handlePressEnter}
        />
      )}
    </div>
  );
}
