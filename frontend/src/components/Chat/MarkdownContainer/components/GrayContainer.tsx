import React from "react";
import styles from "./css/GrayContainer.module.css";
import classNames from "classnames";

type Props = {
  header?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

type LanguageLabelProps = {
  children: string;
  className?: string;
};

const LanguageLabelComponent = ({
  children,
  className,
}: LanguageLabelProps) => {
  return <span className={classNames("text-sm", className)}>{children}</span>;
};

export const LanguageLabel = React.memo(LanguageLabelComponent);

const GrayContainer = ({ header, children, className }: Props) => {
  return (
    <div
      className={classNames(
        "relative flex flex-col my-2",
        styles.container,
        className
      )}
    >
      {header && (
        <div
          className={classNames(
            "w-full h-10 flex items-center justify-between font-mono shadow-xs",
            styles["code-meta"]
          )}
        >
          {header}
        </div>
      )}
      {children}
    </div>
  );
};

export default React.memo(GrayContainer);
