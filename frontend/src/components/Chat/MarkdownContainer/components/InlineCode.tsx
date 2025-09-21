import classNames from "classnames";
import React from "react";

type Props = {
  className?: string;
  children: React.ReactNode;
};

export default function InlineCode({ className, children }: Props) {
  return (
    <code
      className={classNames(
        className,
        "bg-gray-100 px-1 py-0.5 text-sm rounded"
      )}
    >
      {children}
    </code>
  );
}
