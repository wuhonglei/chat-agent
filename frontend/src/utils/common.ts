import { v4 as uuidv4 } from "uuid";

export function getUUID(): string {
  return uuidv4();
}

// 为未登录用户生成匿名 ID
export function getAnonymousUserId(): string {
  const anonymousIdKey = "anonymous_id";
  let anonymousId = localStorage.getItem(anonymousIdKey);
  if (!anonymousId) {
    anonymousId = getUUID();
    localStorage.setItem(anonymousIdKey, anonymousId);
  }

  return anonymousId || "";
}

export function getClientId(): string {
  const clientIdKey = "client_id";
  let clientId = localStorage.getItem(clientIdKey);
  if (!clientId) {
    clientId = getUUID();
    localStorage.setItem(clientIdKey, clientId);
  }

  return clientId || "";
}

// 封装成实用函数
export function prettyCount(num: number, locale = "en-US", digits = 1) {
  return new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: digits,
  }).format(num);
}

/** 本地开发环境下为会话标题加 `dev-` 前缀，避免与线上数据混淆；已带此前缀时不重复添加。 */
export function withDevConversationTitlePrefix(title: string): string {
  if (!import.meta.env.DEV) {
    return title;
  }
  const prefix = "dev-";
  if (title.startsWith(prefix)) {
    return title;
  }
  return `${prefix}${title}`;
}
