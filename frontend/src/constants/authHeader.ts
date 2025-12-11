import { JwtPayload } from "@/interfaces";
import { jwtDecode } from "jwt-decode";

const tokenName = "secret_token_info";
class AuthHeader {
  private secretTokenInfo: string;
  private jwtPayload: JwtPayload | null;
  private readonly userIdKey = "user_id";

  constructor() {
    this.secretTokenInfo = localStorage.getItem(tokenName) || "";
    this.jwtPayload = this.decodeJwtPayload(this.secretTokenInfo);
    this.updateAegisConfig();
  }

  public getJwtPayload(): JwtPayload | null {
    return this.jwtPayload;
  }

  public getAuthorizationHeader(): string {
    return `Bearer ${this.secretTokenInfo}`;
  }

  public setAuthorizationHeader(token: string): void {
    this.secretTokenInfo = token;
    localStorage.setItem(tokenName, token);

    this.jwtPayload = this.decodeJwtPayload(token);
    this.setUserId(this.jwtPayload?.user_id || "");
    this.updateAegisConfig();
  }

  public getUserId(): string {
    return localStorage.getItem(this.userIdKey) || "";
  }

  private setUserId(userId: string): void {
    localStorage.setItem(this.userIdKey, userId);
  }

  private removeUserId(): void {
    localStorage.removeItem(this.userIdKey);
  }

  private updateAegisConfig(): void {
    aegis?.setConfig({
      uin: this.getUserId(),
    });
  }

  public removeAuthorizationHeader(): void {
    this.secretTokenInfo = "";
    localStorage.removeItem(tokenName);
    this.jwtPayload = null;
    this.removeUserId();
    this.updateAegisConfig();
  }

  private decodeJwtPayload(token: string): JwtPayload | null {
    try {
      return jwtDecode(token);
    } catch (error) {
      console.error("Failed to decode JWT payload:", error);
      return null;
    }
  }
}

export const authHeader = new AuthHeader();
