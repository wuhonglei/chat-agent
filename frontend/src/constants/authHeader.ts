import { JwtPayload } from "@/interfaces";
import { jwtDecode } from "jwt-decode";

const tokenName = "secret_token_info";
class AuthHeader {
  private secretTokenInfo: string;
  private jwtPayload: JwtPayload | null;
  constructor() {
    this.secretTokenInfo = localStorage.getItem(tokenName) || "";
    this.jwtPayload = this.decodeJwtPayload(this.secretTokenInfo);
    this.updateAegisConfig();
  }

  public getJwtPayload(): JwtPayload | null {
    return this.jwtPayload;
  }

  public getUserId(): string {
    return this.jwtPayload?.user_id || "";
  }

  public getAuthorizationHeader(): string {
    return `Bearer ${this.secretTokenInfo}`;
  }

  public setAuthorizationHeader(token: string): void {
    this.secretTokenInfo = token;
    localStorage.setItem(tokenName, token);
    this.jwtPayload = this.decodeJwtPayload(token);
    this.updateAegisConfig();
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
