export function jumpToLocation(path: string, replace?: boolean) {
  if (replace) {
    location.replace(path);
  } else {
    location.href = path;
  }
  return;
}

export function isInLoginPage(): boolean {
  return location.pathname.startsWith("/login");
}

export function toLoginPage(redirectUrl?: string): void {
  if (redirectUrl) {
    jumpToLocation("/login?redirect_url=" + redirectUrl, true);
  } else {
    jumpToLocation("/login", true);
  }
  return;
}

export function toChatPage(conversationId?: string): void {
  if (conversationId) {
    jumpToLocation("/chat/" + conversationId, true);
  } else {
    jumpToLocation("/chat", true);
  }
  return;
}
