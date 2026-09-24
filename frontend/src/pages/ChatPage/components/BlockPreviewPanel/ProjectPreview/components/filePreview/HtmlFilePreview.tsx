import React from "react";
import { getDefaultHtmlViewMode } from "../../utils/htmlPreview";
import FileSourceEditor from "./FileSourceEditor";
import PreviewModeShell from "./PreviewModeShell";
import type { SelectedFile } from "./types";

const HTML_IFRAME_SANDBOX =
  "allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-presentation";

const PUBLISHED_HTML_IFRAME_SANDBOX =
  "allow-scripts allow-same-origin allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-pointer-lock allow-presentation allow-top-navigation-by-user-activation";

const IFRAME_CLASS_NAME = "h-full min-h-0 w-full flex-1 border-0 bg-white";

const HtmlFilePreview: React.FC<{
  file: SelectedFile;
  publishedPreviewUrl?: string | null;
}> = ({ file, publishedPreviewUrl }) => {
  const defaultMode = getDefaultHtmlViewMode(file.content, publishedPreviewUrl);
  const preview = publishedPreviewUrl ? (
    <iframe
      title={file.title}
      src={publishedPreviewUrl}
      sandbox={PUBLISHED_HTML_IFRAME_SANDBOX}
      className={IFRAME_CLASS_NAME}
    />
  ) : (
    <iframe
      title={file.title}
      srcDoc={file.content}
      sandbox={HTML_IFRAME_SANDBOX}
      className={IFRAME_CLASS_NAME}
    />
  );

  return (
    <PreviewModeShell
      title={file.title}
      defaultMode={defaultMode}
      preview={preview}
      source={<FileSourceEditor file={file} />}
    />
  );
};

export default HtmlFilePreview;
