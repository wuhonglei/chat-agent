import React from "react";
import styles from "./index.module.css";
import classNames from "classnames";
import { Tooltip } from "antd";

export type CustomButtonProps = {
  active?: boolean;
  bordered?: boolean;
  size?: "small" | "medium" | "large";
  icon?: React.ReactNode;
  children?: React.ReactNode;
  onClick?: (active: boolean) => void;
  className?: string;
  tooltip?: string;
};

const CustomButton = ({
  active = false,
  bordered = true,
  size = "medium",
  icon = null,
  children,
  onClick,
  className,
  tooltip,
}: CustomButtonProps) => {
  return (
    <Tooltip title={tooltip}>
      <div
        onClick={() => onClick?.(!active)}
        className={classNames(
          "inline-flex items-center justify-center",
          bordered && styles.bordered,
          size && styles[size],
          active
            ? "text-blue-500 bg-blue-50"
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
};

export default React.memo(CustomButton);
