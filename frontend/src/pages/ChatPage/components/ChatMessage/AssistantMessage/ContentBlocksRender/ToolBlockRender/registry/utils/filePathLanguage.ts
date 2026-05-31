import { FILE_EXTENSION_LANGUAGE_MAP } from "@/constants";

export function getFilePathFromArgs(args?: Record<string, unknown>): string | undefined {
  const filePath = args?.file_path ?? args?.path;
  return typeof filePath === "string" ? filePath : undefined;
}

export function getLanguageFromFilePath(path: string): string | undefined {
  const ext = path.split(".").pop()?.toLowerCase();
  if (!ext) {
    return undefined;
  }
  return FILE_EXTENSION_LANGUAGE_MAP[ext];
}
