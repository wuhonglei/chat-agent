const HTML_EXTENSIONS = new Set(["html", "htm", "xhtml"]);

const USER_DATA_VIRTUAL_PREFIX = "/mnt/user-data/";

/** 发布站点的静态产物目录（会话相对路径）。 */
export const SITE_OUTPUTS_DIR = "outputs";
export const SITE_DIST_DIR = `${SITE_OUTPUTS_DIR}/app-dist`;

export function isHtmlPath(path: string): boolean {
  const ext = path.split(".").pop()?.toLowerCase();
  return Boolean(ext && HTML_EXTENSIONS.has(ext));
}

/** 将会话相对路径或 present_files 虚拟路径规范为会话相对路径。 */
export function toWorkspaceRelativePath(path: string): string {
  if (path.startsWith(USER_DATA_VIRTUAL_PREFIX)) {
    return path.slice(USER_DATA_VIRTUAL_PREFIX.length);
  }
  return path.replace(/^\/+/, "");
}

/** 路径是否落在可发布的 app-dist 产物下（含入口 index.html）。 */
export function isSiteDistPath(path: string | undefined): boolean {
  if (!path) {
    return false;
  }
  const relative = toWorkspaceRelativePath(path);
  return relative === SITE_DIST_DIR || relative.startsWith(`${SITE_DIST_DIR}/`);
}
