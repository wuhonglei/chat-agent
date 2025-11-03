import classNames from "classnames";
import { useState } from "react";
import { Input } from "antd";

type Props = {
  title: string;
  className?: string;
  onClick: (newTitle: string) => void;
};

export default function HoverButton({
  title,
  onClick,
  className: outerClassName,
}: Props) {
  const [isEdit, setIsEdit] = useState(false);
  const [newTitle, setNewTitle] = useState(title);
  const innerClassName = classNames(
    "h-10 inline-flex items-center justify-center rounded-full px-4 cursor-pointer hover:shadow",
    outerClassName
  );

  const handleBlur = () => {
    setIsEdit(false);
    onClick(newTitle);
  };

  return isEdit ? (
    <Input
      onBlur={handleBlur}
      defaultValue={newTitle}
      onPressEnter={handleBlur}
      className={innerClassName}
      onChange={e => setNewTitle(e.target.value)}
      style={{ display: "inline-flex", width: "auto" }}
    />
  ) : (
    <div className={classNames(innerClassName)} onClick={() => setIsEdit(true)}>
      {title}
    </div>
  );
}
