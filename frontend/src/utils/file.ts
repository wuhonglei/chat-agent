/**
 * 通过 URL 触发浏览器下载。
 *
 * 注意：对普通 http(s) 链接设置 `a.download` 时，若服务端返回了 `Content-Disposition`
 *（例如预览接口里 FileResponse 带 filename），多数浏览器会以响应头里的文件名为准，
 * 从而忽略你在前端传入的 `filename`。
 *
 * 因此在传入非空 `filename` 且 URL 为需覆盖展示名时，先 fetch 再使用 Blob URL 下载，
 * 此时不再经过带 Content-Disposition 的导航，下载名与 `filename` 一致。
 * `blob:` / `data:` 仍走直接点击，避免重复拉取。
 */
export const downloadFileByUrl = async (url: string, filename = ""): Promise<void> => {
  const wantCustomName = Boolean(filename.trim());
  const canFetchOverride = wantCustomName && !url.startsWith("blob:") && !url.startsWith("data:");

  if (canFetchOverride) {
    try {
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      link.rel = "noopener";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
      return;
    } catch {
      // 回退为直接打开链接（文件名可能仍由服务端决定）
    }
  }

  const link = document.createElement("a");
  link.href = url;
  if (filename) {
    link.download = filename;
  }
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
};

export const downloadHtmlContent = (html: string, filename = "document.html") => {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  void downloadFileByUrl(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
};
