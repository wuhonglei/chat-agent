import classNames from "classnames";
import React from "react";

import { computeLineDiff } from "../utils/computeLineDiff";
import styles from "./FileDiffView.module.css";

type FileDiffViewProps = {
  filePath: string | undefined;
  oldString: string;
  newString: string;
  replaceAll?: boolean;
};

const SIGN_BY_TYPE = {
  context: " ",
  added: "+",
  removed: "-",
} as const;

function FileDiffViewImpl({
  filePath,
  oldString,
  newString,
  replaceAll,
}: FileDiffViewProps): React.ReactNode {
  const { lines, added, removed } = React.useMemo(
    () => computeLineDiff(oldString, newString),
    [oldString, newString],
  );

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span className={styles.path} title={filePath}>
          {filePath || "File diff"}
        </span>
        <span className={styles.stats}>
          {replaceAll && <span className={styles.tag}>replace_all</span>}
          {added > 0 && <span className={styles.added}>+{added}</span>}
          {removed > 0 && <span className={styles.removed}>-{removed}</span>}
        </span>
      </div>
      <div className={styles.body}>
        {lines.map((line, index) => (
          <div
            key={index}
            className={classNames(styles.line, {
              [styles.lineContext]: line.type === "context",
              [styles.lineAdded]: line.type === "added",
              [styles.lineRemoved]: line.type === "removed",
            })}
          >
            <span className={styles.sign}>{SIGN_BY_TYPE[line.type]}</span>
            <span className={styles.content}>{line.content || " "}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export const FileDiffView = React.memo(FileDiffViewImpl);
