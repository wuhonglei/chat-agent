import React from "react";
import styles from "./index.module.css";
import classNames from "classnames";

type CustomButtonProps = {
  active?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: (active: boolean) => void;
};

export default function CustomButton({
  active = false,
  icon = null,
  children,
  onClick,
}: CustomButtonProps) {
  return (
    <div
      onClick={() => onClick?.(!active)}
      className={classNames(
        "inline-flex items-center py-2.5 px-4",
        active
          ? "text-blue-500 bg-blue-50"
          : "border-gray-500 hover:bg-gray-100",
        styles.button
      )}
    >
      {icon && <div className="mr-1">{icon}</div>}
      {children}
    </div>
  );
}
