export function isLoginPage(): boolean {
  return location.pathname.includes("/login");
}

export function isUnAuthorized(status: number): boolean {
  return status === 401;
}

export function redirectToLogin(redirect?: string): void {
  if (isLoginPage()) {
    console.info("already in login page");
    return;
  }

  if (redirect) {
    location.replace("/login?redirect=" + redirect);
  } else {
    location.replace("/login");
  }
  return;
}
