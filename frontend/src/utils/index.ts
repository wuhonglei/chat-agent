export function getWebIconUrl(url: string, size: number = 32) {
  const urlObj = new URL(url);
  return `https://www.google.com/s2/favicons?domain=${urlObj.hostname}&sz=${size}`;
}
