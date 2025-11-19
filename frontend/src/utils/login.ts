import { isInLoginPage, toLoginPage } from "./location";

export function isUnAuthorized(status: number): boolean {
  return status === 401;
}

export function redirectToLogin(redirectUrl?: string): void {
  if (isInLoginPage()) {
    console.info("already in login page");
    return;
  }

  toLoginPage(redirectUrl);
  return;
}
