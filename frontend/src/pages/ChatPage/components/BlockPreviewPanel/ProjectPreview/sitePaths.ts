const HTML_EXTENSIONS = new Set(["html", "htm", "xhtml"]);

const USER_DATA_VIRTUAL_PREFIX = "/mnt/user-data/";

/** 发布站点的静态产物目录（会话相对路径）。 */
export const SITE_OUTPUTS_DIR = "outputs";
export const SITE_DIST_DIR = `${SITE_OUTPUTS_DIR}/app-dist`;
export const SITE_OUTPUTS_INDEX = `${SITE_OUTPUTS_DIR}/index.html`;

/** 发布接口使用的虚拟路径。 */
export const SITE_VIRTUAL_OUTPUTS = `${USER_DATA_VIRTUAL_PREFIX}${SITE_OUTPUTS_DIR}`;
export const SITE_VIRTUAL_DIST = `${USER_DATA_VIRTUAL_PREFIX}${SITE_DIST_DIR}`;

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

/** outputs 根目录下的 HTML（不含 app-dist）。 */
export function isOutputsRootHtmlPath(path: string | undefined): boolean {
  if (!path || !isHtmlPath(path)) {
    return false;
  }
  const relative = toWorkspaceRelativePath(path);
  if (isSiteDistPath(relative)) {
    return false;
  }
  const prefix = `${SITE_OUTPUTS_DIR}/`;
  if (!relative.startsWith(prefix)) {
    return false;
  }
  const rest = relative.slice(prefix.length);
  return rest.length > 0 && !rest.includes("/");
}

/** 路径是否可作为发布入口（app-dist、outputs 根、或 outputs 根下的 HTML）。 */
export function isPublishableSitePath(path: string | undefined): boolean {
  if (!path) {
    return false;
  }
  const relative = toWorkspaceRelativePath(path);
  return relative === SITE_OUTPUTS_DIR || isSiteDistPath(relative) || isOutputsRootHtmlPath(relative);
}

export function resolvePublishSource(options: {
  hasAppDist: boolean;
  hasOutputsIndex: boolean;
}): string {
  if (options.hasAppDist) {
    return SITE_VIRTUAL_DIST;
  }
  if (options.hasOutputsIndex) {
    return SITE_VIRTUAL_OUTPUTS;
  }
  return SITE_VIRTUAL_DIST;
}
