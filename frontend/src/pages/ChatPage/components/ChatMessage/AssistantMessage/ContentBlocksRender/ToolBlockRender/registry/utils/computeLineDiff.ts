export type DiffLineType = "context" | "added" | "removed";

export interface DiffLine {
  type: DiffLineType;
  content: string;
  oldNumber?: number;
  newNumber?: number;
}

export interface LineDiffResult {
  lines: DiffLine[];
  added: number;
  removed: number;
}

const MAX_LCS_CELLS = 4_000_000;

function fallbackDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  const lines: DiffLine[] = [];
  let oldNo = 1;
  let newNo = 1;
  for (const content of oldLines) {
    lines.push({ type: "removed", content, oldNumber: oldNo++ });
  }
  for (const content of newLines) {
    lines.push({ type: "added", content, newNumber: newNo++ });
  }
  return lines;
}

/**
 * 基于 LCS 的逐行差异，用于以 git diff 的形式展示文件编辑前后的变化。
 * 当行数过大导致 DP 矩阵超出阈值时，退化为「整段删除 + 整段新增」以避免内存压力。
 */
export function computeLineDiff(oldText: string, newText: string): LineDiffResult {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const n = oldLines.length;
  const m = newLines.length;

  let lines: DiffLine[];

  if ((n + 1) * (m + 1) > MAX_LCS_CELLS) {
    lines = fallbackDiff(oldLines, newLines);
  } else {
    const dp: number[][] = Array.from({ length: n + 1 }, () =>
      Array.from<number>({ length: m + 1 }).fill(0),
    );
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] =
          oldLines[i] === newLines[j]
            ? dp[i + 1][j + 1] + 1
            : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }

    lines = [];
    let i = 0;
    let j = 0;
    let oldNo = 1;
    let newNo = 1;
    while (i < n && j < m) {
      if (oldLines[i] === newLines[j]) {
        lines.push({ type: "context", content: oldLines[i], oldNumber: oldNo++, newNumber: newNo++ });
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) {
        lines.push({ type: "removed", content: oldLines[i], oldNumber: oldNo++ });
        i++;
      } else {
        lines.push({ type: "added", content: newLines[j], newNumber: newNo++ });
        j++;
      }
    }
    while (i < n) {
      lines.push({ type: "removed", content: oldLines[i], oldNumber: oldNo++ });
      i++;
    }
    while (j < m) {
      lines.push({ type: "added", content: newLines[j], newNumber: newNo++ });
      j++;
    }
  }

  let added = 0;
  let removed = 0;
  for (const line of lines) {
    if (line.type === "added") {
      added++;
    } else if (line.type === "removed") {
      removed++;
    }
  }

  return { lines, added, removed };
}
