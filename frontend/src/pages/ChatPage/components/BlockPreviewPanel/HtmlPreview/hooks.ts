import { useEffect, useState } from "react";

export const useHtmlPreviewUrl = (content: string) => {
  const [previewUrl, setPreviewUrl] = useState<string>();

  useEffect(() => {
    if (!content.trim()) {
      setPreviewUrl(undefined);
      return;
    }

    const blob = new Blob([content], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [content]);

  return previewUrl;
};
