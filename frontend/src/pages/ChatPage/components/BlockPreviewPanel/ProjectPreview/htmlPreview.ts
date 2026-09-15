import {
  SITE_DIST_DIR,
  SITE_OUTPUTS_DIR,
  isHtmlPath,
  isSiteDistPath,
  toWorkspaceRelativePath,
} from "./sitePaths";

export type HtmlViewMode = "preview" | "source";

/** 达到该行数的 HTML 视为可直接 srcDoc 预览的纯静态页。 */
export const HTML_PREVIEW_MIN_LINES = 50;

const INDEX_HTML_FILE_PATTERN = /(^|\/)index\.html?$/i;

export function countTextLines(content: string): number {
  if (!content) {
    return 0;
  }
  return content.split(/\r?\n/).length;
}

/**
 * HTML 默认视图：源码。已发布的站点页、或行数达到阈值时改为预览。
 * 发布地址来自站点 API 的 url，不要从 HTML 源码正则抽取（产物里通常没有公网域名）。
 */
export function getDefaultHtmlViewMode(
  content: string,
  publishedPreviewUrl?: string | null,
): HtmlViewMode {
  if (publishedPreviewUrl) {
    return "preview";
  }
  if (countTextLines(content) >= HTML_PREVIEW_MIN_LINES) {
    return "preview";
  }
  return "source";
}

function siteRelativeRest(relative: string): string | null {
  if (isSiteDistPath(relative)) {
    return relative === SITE_DIST_DIR ? "" : relative.slice(SITE_DIST_DIR.length + 1);
  }
  if (relative === SITE_OUTPUTS_DIR) {
    return "";
  }
  const outputsPrefix = `${SITE_OUTPUTS_DIR}/`;
  if (relative.startsWith(outputsPrefix)) {
    return relative.slice(outputsPrefix.length);
  }
  return null;
}

function toPublishedUrl(origin: string, rest: string): string {
  if (!rest || INDEX_HTML_FILE_PATTERN.test(rest)) {
    const dir = rest.replace(INDEX_HTML_FILE_PATTERN, "").replace(/\/+$/, "");
    return dir ? `${origin}/${dir}/` : `${origin}/`;
  }
  return `${origin}/${rest}`;
}

/** 将会话内 outputs / app-dist HTML 映射到已发布站点上的对应 URL。 */
export function getPublishedHtmlPreviewUrl(
  filePath: string | null | undefined,
  siteUrl: string | null | undefined,
): string | null {
  if (!filePath || !siteUrl || !isHtmlPath(filePath)) {
    return null;
  }
  const relative = toWorkspaceRelativePath(filePath);
  const rest = siteRelativeRest(relative);
  if (rest == null) {
    return null;
  }
  const origin = siteUrl.replace(/\/+$/, "");
  return toPublishedUrl(origin, rest);
}
