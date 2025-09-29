import { capitalize } from "lodash-es";
import { SearchSourceType } from "@/constants";

/**
 * 私有域名到公共域名的映射
 */
const hostnameToPublic = {
  "confluence.shopee.io": "www.atlassian.com",
};
type PrivateDomains = keyof typeof hostnameToPublic;

export function getWebIconUrl(url: string | undefined, size: number = 32) {
  if (!url) return "";
  try {
    const urlObj = new URL(url);
    const hostname =
      hostnameToPublic[urlObj.hostname as PrivateDomains] || urlObj.hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=${size}`;
  } catch (error) {
    return "";
  }
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

export function isInputEnter(event: React.KeyboardEvent<HTMLTextAreaElement>) {
  // 只有按下回车键才发送, 组合键shift+enter不发送
  if (event.key !== "Enter" || event.shiftKey) {
    return false;
  }

  // 中文输入法下，按下回车键不发送
  if (event.nativeEvent.isComposing) {
    return false;
  }

  return true;
}

export function isFromConfluence(sourceType: SearchSourceType) {
  return sourceType === SearchSourceType.CONFLUENCE;
}

export function isFromWebSearch(sourceType: SearchSourceType) {
  return sourceType === SearchSourceType.WEB_SEARCH;
}
