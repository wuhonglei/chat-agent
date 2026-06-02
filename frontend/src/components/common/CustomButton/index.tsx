import { Tooltip } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import classNames from "classnames";
import React, { forwardRef } from "react";
import styles from "./index.module.css";

export type CustomButtonProps = {
  active?: boolean;
  bordered?: boolean;
  disabled?: boolean;
  size?: SizeType;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  onClick?: (active: boolean) => void;
  className?: string;
  tooltip?: string;
};

const CustomButton = forwardRef<HTMLDivElement, CustomButtonProps>(
  (
    {
      active = false,
      bordered = true,
      disabled = false,
      size = "middle",
      icon = null,
      children,
      onClick,
      className,
      tooltip,
    },
    ref
  ) => {
    const handleClick = () => {
      if (disabled) {
        return;
      }
      onClick?.(!active);
    };

    return (
      <Tooltip title={tooltip} getTooltipContainer={(trigger: HTMLElement) => trigger.parentElement ?? document.body}>
        <div
          ref={ref}
          onClick={handleClick}
          className={classNames(
            "inline-flex items-center justify-center",
            bordered && styles.bordered,
            size && styles[size],
            active ? "text-primary bg-blue-50" : "border-gray-500 hover:bg-gray-100",
            disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
            styles.button,
            className
          )}
        >
          {icon && <span className="mr-1">{icon}</span>}
          {children}
        </div>
      </Tooltip>
    );
  }
);

export default React.memo(CustomButton);
