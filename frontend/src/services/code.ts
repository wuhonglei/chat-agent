import type { CodeExecBlock, CodeRuntimeLanguage } from "@/interfaces/contentBlock";
import { apiClient } from "./base";

export type CodeExecResponse = Pick<CodeExecBlock, "language" | "version" | "run" | "compile">;

export interface ExecuteCodeRequest {
  code: string;
  language: CodeRuntimeLanguage;
}

export const codeAPI = {
  executeCode: async (payload: ExecuteCodeRequest): Promise<CodeExecResponse> => {
    return await apiClient.post("/code/execute", payload);
  },
};
