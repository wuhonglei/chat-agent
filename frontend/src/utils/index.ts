import { capitalize } from "lodash-es";

export function getWebIconUrl(url: string | undefined, size: number = 32) {
  if (!url) return "";
  const urlObj = new URL(url);
  return `https://www.google.com/s2/favicons?domain=${urlObj.hostname}&sz=${size}`;
}

export function getWebMainDomain(
  url: string | undefined,
  capitalizeFirstLetter: boolean = false
) {
  if (!url) return "";
  const urlObj = new URL(url);
  const hostname = urlObj.hostname;
  const hostnamePart = hostname.split(".");
  if (hostnamePart.length > 2) {
    hostnamePart.shift(); // 移除顶级域名
  }
  const mainDomain = hostnamePart[0];
  return capitalizeFirstLetter ? capitalize(mainDomain) : mainDomain;
}
