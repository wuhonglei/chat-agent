import { InputNumber, Typography } from "antd";
import React, { useEffect, useState } from "react";

export interface PaginationControlProps {
  numPages: number;
  pageNumber: number;
  onPageNumberChange: (pageNumber: number) => void;
}

const PaginationControl: React.FC<PaginationControlProps> = ({ numPages, pageNumber, onPageNumberChange }) => {
  const [pendingPageNumber, setPendingPageNumber] = useState<number | null>(pageNumber);

  useEffect(() => {
    setPendingPageNumber(pageNumber);
  }, [pageNumber]);

  const commitPendingPageNumber = () => {
    if (numPages <= 0 || pendingPageNumber == null || !Number.isFinite(pendingPageNumber)) {
      setPendingPageNumber(pageNumber);
      return;
    }
    const clampedPageNumber = Math.min(Math.max(Math.trunc(pendingPageNumber), 1), numPages);
    onPageNumberChange(clampedPageNumber);
    setPendingPageNumber(clampedPageNumber);
  };

  return (
    <div className="flex items-center gap-2">
      <InputNumber
        value={pendingPageNumber}
        min={1}
        max={Math.max(numPages, 1)}
        disabled={numPages <= 0}
        size="small"
        controls={false}
        onPressEnter={commitPendingPageNumber}
        onBlur={() => setPendingPageNumber(pageNumber)}
        style={{ width: 32, backgroundColor: "var(--color-fill-content)" }}
        onChange={value => setPendingPageNumber(typeof value === "number" ? value : null)}
      />
      <Typography.Text type="secondary">/ {numPages > 0 ? numPages : "-"}</Typography.Text>
    </div>
  );
};

export default React.memo(PaginationControl);
