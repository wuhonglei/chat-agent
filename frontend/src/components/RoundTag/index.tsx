import React from "react";
import classNames from "classnames";

type Props = {
  className?: string;
  interactive?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
  [key: string]: any;
};

export default function RoundTag({
  children,
  className,
  style,
  interactive,
  ...props
}: Props) {
  const restProps = interactive ? props : {};

  return (
    <button
      className={classNames(
        "rounded-full h-4.5 px-1 min-w-4.5 text-center not-italic text-xs bg-gray-200 transition",
        interactive && "hover:bg-gray-300 cursor-pointer",
        className
      )}
      style={style}
      {...restProps}
    >
      {children}
    </button>
  );
}
