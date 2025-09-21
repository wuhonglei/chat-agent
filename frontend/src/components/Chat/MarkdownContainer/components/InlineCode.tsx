import classNames from "classnames";
import React from "react";

type Props = {
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
};

export default function InlineCode({ className, children, style }: Props) {
  return (
    <code
      className={classNames(
        "bg-gray-100 px-1 py-0.5 text-sm rounded",
        className
      )}
      style={style}
    >
      {children}
    </code>
  );
}
