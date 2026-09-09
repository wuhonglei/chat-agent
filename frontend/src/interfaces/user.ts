export interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
  phone: string;
  /** 用户角色：user / admin */
  role?: string;
}

/** 与 mem0 governance_status 对齐；缺省视为 active */
export type MemoryGovernanceStatus = "active" | "merged" | "superseded" | "archived";

/** 与 mem0 memory_kind 对齐；pattern 为治理合成，缺省为普通记忆 */
export type MemoryKind = "pattern";

export type MemoryRole = "user" | "assistant";

/** 用户记忆单条（axios 会把后端 snake_case 转成 camelCase） */
export interface MemoryListItem {
  id: string;
  memory: string;
  hash?: string | null;
  metadata?: Record<string, unknown> | null;
  createdAt: string;
  updatedAt?: string | null;
  userId?: string | null;
  role?: MemoryRole | null;
  score?: number | null;
  governanceStatus?: MemoryGovernanceStatus | null;
  memoryKind?: MemoryKind | null;
  synthesizedFrom?: string[] | null;
  governancePassId?: string | null;
  governanceTimestamp?: string | null;
  synthesisEvidenceHash?: string | null;
  mergedInto?: string | null;
  supersededBy?: string | null;
}

/** 用户记忆列表 */
export interface MemoryListResponse {
  memories: MemoryListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface MemoryListParams {
  page?: number;
  pageSize?: number;
}
