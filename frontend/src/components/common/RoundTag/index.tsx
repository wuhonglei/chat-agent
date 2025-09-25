import React, { forwardRef } from "react";
import classNames from "classnames";

type Props = {
  className?: string;
  interactive?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
  [key: string]: any;
};

const RoundTag = forwardRef<HTMLButtonElement, Props>(
  ({ children, className, style, interactive, ...props }, ref) => {
    const restProps = interactive ? props : {};

    return (
      <button
        ref={ref}
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
);

export default React.memo(RoundTag);
