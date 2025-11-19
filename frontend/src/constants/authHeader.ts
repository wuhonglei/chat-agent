const tokenName = "secret_token_info";
class AuthHeader {
  private secretTokenInfo: string;
  constructor() {
    this.secretTokenInfo = localStorage.getItem(tokenName) || "";
  }

  public getAuthorizationHeader(): string {
    return `Bearer ${this.secretTokenInfo}`;
  }

  public setAuthorizationHeader(token: string): void {
    this.secretTokenInfo = token;
    localStorage.setItem(tokenName, token);
  }

  public removeAuthorizationHeader(): void {
    this.secretTokenInfo = "";
    localStorage.removeItem(tokenName);
  }
}

export const authHeader = new AuthHeader();
