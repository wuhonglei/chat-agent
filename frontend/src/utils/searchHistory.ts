const STORAGE_KEY = "conversation-search-history:v1";
const MAX_HISTORY = 20;

function readRaw(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is string => typeof item === "string" && item.trim().length > 0,
    );
  } catch {
    return [];
  }
}

function writeRaw(items: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_HISTORY)));
  } catch {
    // ignore quota / private mode
  }
}

export function getSearchHistory(): string[] {
  return readRaw();
}

export function addSearchHistory(keyword: string): string[] {
  const trimmed = keyword.trim();
  if (!trimmed) return readRaw();
  const next = [trimmed, ...readRaw().filter((item) => item !== trimmed)].slice(0, MAX_HISTORY);
  writeRaw(next);
  return next;
}

export function removeSearchHistory(keyword: string): string[] {
  const next = readRaw().filter((item) => item !== keyword);
  writeRaw(next);
  return next;
}

export function clearSearchHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
