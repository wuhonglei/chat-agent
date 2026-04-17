import classNames from "classnames";
import React from "react";
import styles from "./index.module.css";

type Props = {
  children: React.ReactNode;
  className?: string;
};

const CustomHeader = ({ children, className }: Props) => {
  return <div className={classNames(styles.header, className)}>{children}</div>;
};

export default React.memo(CustomHeader);
