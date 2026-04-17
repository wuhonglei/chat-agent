export const downloadFileByUrl = (url: string, filename = "") => {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
};

export const downloadHtmlContent = (html: string, filename = "document.html") => {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  downloadFileByUrl(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
};
