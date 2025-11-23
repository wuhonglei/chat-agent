import classNames from "classnames";
import React, { forwardRef } from "react";

type Props = {
  className?: string;
  interactive?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
  onClick?: () => void;
};

const RoundTag = forwardRef<HTMLButtonElement, Props>(
  ({ children, className, style, interactive, onClick, ...props }, ref) => {
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
        onClick={onClick}
        {...restProps}
      >
        {children}
      </button>
    );
  }
);

export default React.memo(RoundTag);
