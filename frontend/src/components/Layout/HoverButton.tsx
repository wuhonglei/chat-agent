import classNames from "classnames";
import { useState, useEffect, useRef } from "react";
import { App, Input } from "antd";
import { useClickAway } from "ahooks";

type Props = {
  title: string;
  className?: string;
  onConfirm: (newTitle: string) => void;
};

export default function HoverButton({
  title,
  onConfirm,
  className: outerClassName,
}: Props) {
  const [isEdit, setIsEdit] = useState(false);
  const { message } = App.useApp();
  const [newTitle, setNewTitle] = useState(title);
  const containerRef = useRef<HTMLDivElement>(null);

  // 当 title prop 变化时，同步更新 newTitle
  useEffect(() => {
    setNewTitle(title);
  }, [title]);

  function resetNewTitle() {
    setNewTitle(title);
  }

  function validateAndConfirm() {
    if (!isEdit) {
      return;
    }

    const trimmedNewTitle = newTitle.trim();
    setIsEdit(false);
    if (!trimmedNewTitle) {
      message.warning("标题不能为空");
      resetNewTitle();
      return;
    }

    if (trimmedNewTitle === title) {
      resetNewTitle();
      return;
    }

    if (trimmedNewTitle.length > 30) {
      message.warning("标题不能超过30个字符");
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
