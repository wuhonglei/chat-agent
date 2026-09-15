import { apiClient } from "./base";

export interface PublishedSite {
  slug: string;
  version: number;
  url: string;
  visibility: string;
  sizeBytes: number;
  expiresAt: string | null;
  conversationId: string;
  unpublishedAt: string | null;
  entry: string;
  fileCount?: number | null;
}

export interface PublishSitePayload {
  conversationId: string;
  source?: string;
  slug?: string;
  visibility?: "unlisted" | "public";
}

export const sitesAPI = {
  listMine: async (): Promise<PublishedSite[]> => {
    return await apiClient.get("/sites/me");
  },
  publish: async (payload: PublishSitePayload): Promise<PublishedSite> => {
    const body: Record<string, unknown> = {
      conversationId: payload.conversationId,
      visibility: payload.visibility || "unlisted",
    };
    if (payload.source) {
      body.source = payload.source;
    }
    if (payload.slug) {
      body.slug = payload.slug;
    }
    return await apiClient.post("/sites/", body);
  },
  republish: async (
    slug: string,
    payload?: Pick<PublishSitePayload, "source" | "visibility">
  ): Promise<PublishedSite> => {
    const body: Record<string, unknown> = {};
    if (payload?.source) {
      body.source = payload.source;
    }
    if (payload?.visibility) {
      body.visibility = payload.visibility;
    }
    return await apiClient.post(`/sites/${encodeURIComponent(slug)}/republish`, body);
  },
  unpublish: async (slug: string): Promise<PublishedSite> => {
    return await apiClient.delete(`/sites/${encodeURIComponent(slug)}`);
  },
};
