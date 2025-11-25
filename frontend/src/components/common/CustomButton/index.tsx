import { Tooltip } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import classNames from "classnames";
import React, { forwardRef } from "react";
import styles from "./index.module.css";

export type CustomButtonProps = {
  active?: boolean;
  bordered?: boolean;
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
      size = "middle",
      icon = null,
      children,
      onClick,
      className,
      tooltip,
    },
    ref
  ) => {
    return (
      <Tooltip
        title={tooltip}
        getTooltipContainer={(trigger: HTMLElement) =>
          trigger.parentElement ?? document.body
        }
      >
        <div
          ref={ref}
          onClick={() => onClick?.(!active)}
          className={classNames(
            "inline-flex items-center justify-center",
            bordered && styles.bordered,
            size && styles[size],
            active
              ? "text-primary bg-blue-50"
              : "border-gray-500 hover:bg-gray-100",
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
