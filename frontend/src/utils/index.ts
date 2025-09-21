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
  let hostname = urlObj.hostname;
  hostname = hostname.replace(/^(www|m|mobile)\./, "");
  hostname = hostname.split(".")[0];
  return capitalizeFirstLetter ? capitalize(hostname) : hostname;
}
