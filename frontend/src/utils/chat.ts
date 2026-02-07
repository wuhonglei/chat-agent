import { ChatMessage, MessageStatus, RoleType, SearchSource, SearchSourceType, ToolCallStatus } from "@/interfaces";
import { capitalize, isEmpty, isNil } from "lodash-es";

/**
 * 构建脚注定义
 * @param footnotes 脚注列表
 * @returns 脚注定义
 */
export function buildFootnoteDefinition(sources: SearchSource[]): string {
  return sources.map((source, index) => `[^CITE:${index + 1}]: ${source.title || index + 1}`).join("\n");
}

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
    const hostname = hostnameToPublic[urlObj.hostname as PrivateDomains] || urlObj.hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=${size}`;
  } catch {
    return "";
  }
}

export function getSortedIconUrl(url: string | undefined, favicon: string | undefined) {
  return favicon || getWebIconUrl(url);
}

export function getWebMainDomain(url: string | undefined, capitalizeFirstLetter: boolean = false) {
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

/**
 * 判断是否是输入回车键
 * @param event 键盘事件
 * @returns 是否是输入回车键
 */
export function isInputEnter(event: React.KeyboardEvent<Element>) {
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
  return sourceType === SearchSourceType.Confluence;
}

export function isFromWebSearch(sourceType: SearchSourceType) {
  return sourceType === SearchSourceType.WebSearch;
}

export function isUserRole(role: RoleType) {
  return role === "user";
}

export function isAssistantRole(role: RoleType) {
  return role === "assistant";
}

export function isSystemRole(role: RoleType) {
  return role === "system";
}

/**
 * 获取历史消息
 * 注意: 函数体中的 messages 使用的是旧的消息列表，不是最新的消息列表
 */
export function getHistoryMessageIds<T extends ChatMessage>(limit: number, messages: T[], index?: number): string[] {
  const histories = isNil(index) ? messages.slice(-limit) : messages.slice(Math.max(0, index - limit), index);
  const validHistoryIds: string[] = [];
  for (let i = 0; i < histories.length - 1; i) {
    const message = histories[i];
    const nextMessage = histories[i + 1];
    if (
      isUserRole(message.role) &&
      isAssistantRole(nextMessage.role) &&
      !isEmpty(nextMessage.content) &&
      nextMessage.status === MessageStatus.Done
    ) {
      validHistoryIds.push(message.id, nextMessage.id);
      i += 2;
    } else {
      i += 1;
    }
  }
  return validHistoryIds;
}

/**
 * 获取需要删除的消息ID
 * @param messages
 * @param index
 * @returns
 */
export function getRemovedMessageIds(messages: ChatMessage[], index?: number): string[] {
  if (isNil(index)) {
    return [];
  }

  const removedMessages = messages.slice(index);
  return removedMessages.map(message => message.id);
}

export function isCallingTool(status: ToolCallStatus) {
  return status === ToolCallStatus.CallingTool;
}
