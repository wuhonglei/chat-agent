import type { ChatMessage } from "@/interfaces";
import { MessageStatus } from "@/interfaces";
import type { UserAttachmentBlock } from "@/interfaces/contentBlock";
import { describe, expect, it } from "vite-plus/test";
import {
  applyMentionToText,
  buildMentionTagSlot,
  collectMentionableAttachments,
  filterMentionableByQuery,
  getActiveMention,
  getAttachmentDisplayName,
  getMentionReplaceCharacters,
  isMentionableAttachment,
} from "./attachmentMention";

function makePdf(id: string, name?: string): UserAttachmentBlock {
  return {
    id,
    type: "pdf",
    url: `/api/file/preview/u/${id}.pdf`,
    name,
    size: 100,
    mime: "application/pdf",
  };
}

function makeImage(id: string, name?: string): UserAttachmentBlock {
  return {
    id,
    type: "image",
    url: `/api/file/preview/u/${id}.png`,
    name,
    size: 50,
    mime: "image/png",
  };
}

function makeUserMessage(blocks: UserAttachmentBlock[]): ChatMessage {
  return {
    id: "msg-1",
    role: "user",
    contentBlocks: [{ id: "t1", type: "text", text: "hello" }, ...blocks],
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    status: MessageStatus.Done,
    messageMetadata: {
      content: "hello",
      thinkMode: false,
      agentMode: 0,
      modelID: "",
    },
    replyTo: "",
  };
}

describe("isMentionableAttachment", () => {
  it("excludes images and keeps document attachments", () => {
    expect(isMentionableAttachment(makeImage("img"))).toBe(false);
    expect(isMentionableAttachment(makePdf("pdf"))).toBe(true);
  });
});

describe("getAttachmentDisplayName", () => {
  it("uses name when present and falls back by type", () => {
    expect(getAttachmentDisplayName(makePdf("p1", "report.pdf"))).toBe("report.pdf");
    expect(getAttachmentDisplayName(makePdf("p2"))).toBe("document.pdf");
    expect(getAttachmentDisplayName(makeImage("i1"))).toBe("image.png");
  });
});

describe("collectMentionableAttachments", () => {
  it("excludes images, dedupes by id, and prefers current-turn blocks", () => {
    const historyPdf = makePdf("same-id", "history.pdf");
    const currentPdf = makePdf("same-id", "current.pdf");
    const otherPdf = makePdf("other", "other.pdf");
    const image = makeImage("img", "photo.png");

    const result = collectMentionableAttachments({
      messages: [makeUserMessage([historyPdf, otherPdf, image])],
      currentAttachmentBlocks: [currentPdf],
    });

    expect(result).toHaveLength(2);
    expect(result.find(item => item.id === "same-id")?.name).toBe("current.pdf");
    expect(result.some(item => item.id === "other")).toBe(true);
    expect(result.some(item => item.type === "image")).toBe(false);
  });
});

describe("getActiveMention", () => {
  it("detects trailing @query and returns null otherwise", () => {
    expect(getActiveMention("请看 @rep")).toEqual({ query: "rep", atIndex: 3 });
    expect(getActiveMention("请看 @")).toEqual({ query: "", atIndex: 3 });
    expect(getActiveMention("请看 @report.pdf 继续")).toBeNull();
    expect(getActiveMention("email@x.com")).toBeNull();
  });
});

describe("filterMentionableByQuery", () => {
  it("filters by display name case-insensitively", () => {
    const attachments = [makePdf("a", "Report.pdf"), makePdf("b", "notes.md")];
    expect(filterMentionableByQuery(attachments, "rep").map(item => item.id)).toEqual(["a"]);
    expect(filterMentionableByQuery(attachments, "").map(item => item.id)).toEqual(["a", "b"]);
  });
});

describe("buildMentionTagSlot", () => {
  it("builds a tag slot with @displayName label and formatResult", () => {
    const slot = buildMentionTagSlot(makePdf("p1", "report.pdf"));
    expect(slot.type).toBe("tag");
    expect(slot.props.label).toBe("@report.pdf");
    expect(slot.props.value).toBe("p1");
    expect(slot.formatResult()).toBe("@report.pdf ");
    expect(slot.key.startsWith("mention_p1_")).toBe(true);
  });
});

describe("getMentionReplaceCharacters", () => {
  it("prefixes query with @", () => {
    expect(getMentionReplaceCharacters("rep")).toBe("@rep");
    expect(getMentionReplaceCharacters("")).toBe("@");
  });
});

describe("applyMentionToText", () => {
  it("replaces active @query with @displayName and a trailing space", () => {
    expect(applyMentionToText("请看 @rep", 3, "rep", "report.pdf")).toBe("请看 @report.pdf ");
    expect(applyMentionToText("@", 0, "", "a.pdf")).toBe("@a.pdf ");
  });
});
