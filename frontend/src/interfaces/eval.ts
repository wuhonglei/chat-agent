/** Bad Case 入队来源 */
export type BadCaseSource = "rule_fail" | "low_score" | "thumb_down";

/** Bad Case 复核状态 */
export type BadCaseStatus = "pending" | "reviewing" | "resolved" | "dismissed";

/** Bad Case 归因分类 */
export type BadCaseAttribution =
  | "retrieval_miss"
  | "tool_failure"
  | "model_capability"
  | "context_loss"
  | "annotation_issue"
  | "hallucination"
  | "other";

/** Bad Case 处理方式 */
export type BadCaseResolution = "added_to_dataset" | "prompt_fix" | "model_upgrade" | "annotation_fixed" | "no_action";

export interface BadCaseItem {
  id: string;
  source: BadCaseSource;
  messageId: string | null;
  conversationId: string | null;
  userId: string | null;
  query: string;
  answer: string;
  ruleScores: Record<string, unknown>;
  judgeScores: Record<string, unknown> | null;
  traceId: string | null;
  langfuseTraceUrl: string | null;
  feedbackReasons: string[];
  feedbackComment: string | null;
  status: BadCaseStatus;
  attribution: BadCaseAttribution | null;
  reviewerNotes: string | null;
  resolution: BadCaseResolution | null;
  createdAt: string;
  reviewedAt: string | null;
  resolvedAt: string | null;
}

export interface BadCaseListResponse {
  items: BadCaseItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BadCaseStatsResponse {
  total: number;
  byStatus: Record<string, number>;
  bySource: Record<string, number>;
  byAttribution: Record<string, number>;
}

export interface BadCaseUpdateRequest {
  status?: BadCaseStatus;
  attribution?: BadCaseAttribution | null;
  reviewerNotes?: string | null;
  resolution?: BadCaseResolution | null;
}

export interface BadCaseListParams {
  status?: BadCaseStatus;
  source?: BadCaseSource;
  attribution?: BadCaseAttribution;
  page?: number;
  pageSize?: number;
}
