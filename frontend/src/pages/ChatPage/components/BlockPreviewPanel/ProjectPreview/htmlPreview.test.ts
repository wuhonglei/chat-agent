import { describe, expect, it } from "vite-plus/test";
import {
  HTML_PREVIEW_MIN_LINES,
  countTextLines,
  getDefaultHtmlViewMode,
  getPublishedHtmlPreviewUrl,
} from "./htmlPreview";

describe("countTextLines", () => {
  it("returns 0 for empty content", () => {
    expect(countTextLines("")).toBe(0);
  });

  it("counts a single line without newline as 1", () => {
    expect(countTextLines("<html></html>")).toBe(1);
  });

  it("counts both lf and crlf lines", () => {
    expect(countTextLines("a\nb\nc")).toBe(3);
    expect(countTextLines("a\r\nb\r\nc")).toBe(3);
  });
});

describe("getDefaultHtmlViewMode", () => {
  it("defaults to source for short html", () => {
    expect(getDefaultHtmlViewMode("<html></html>")).toBe("source");
  });

  it("defaults to preview when published url exists", () => {
    expect(
      getDefaultHtmlViewMode("<html></html>", "https://resume-site.apps.wuhonglei.cn/"),
    ).toBe("preview");
  });

  it("defaults to preview when line count reaches the threshold", () => {
    const content = Array.from({ length: HTML_PREVIEW_MIN_LINES }, (_, i) => `<p>${i}</p>`).join(
      "\n",
    );
    expect(getDefaultHtmlViewMode(content)).toBe("preview");
  });

  it("stays source just below the threshold", () => {
    const content = Array.from({ length: HTML_PREVIEW_MIN_LINES - 1 }, (_, i) => `<p>${i}</p>`).join(
      "\n",
    );
    expect(getDefaultHtmlViewMode(content)).toBe("source");
  });
});

describe("getPublishedHtmlPreviewUrl", () => {
  const siteUrl = "https://resume-site.apps.wuhonglei.cn";

  it("returns null when site is unpublished or path is not html in app-dist", () => {
    expect(getPublishedHtmlPreviewUrl("outputs/app-dist/index.html", undefined)).toBeNull();
    expect(getPublishedHtmlPreviewUrl("workspace/index.html", siteUrl)).toBeNull();
    expect(getPublishedHtmlPreviewUrl("outputs/app-dist/main.js", siteUrl)).toBeNull();
  });

  it("maps app-dist index.html to the site origin", () => {
    expect(getPublishedHtmlPreviewUrl("outputs/app-dist/index.html", siteUrl)).toBe(`${siteUrl}/`);
    expect(
      getPublishedHtmlPreviewUrl("/mnt/user-data/outputs/app-dist/index.html", `${siteUrl}/`),
    ).toBe(`${siteUrl}/`);
  });

  it("maps nested html files to the corresponding public path", () => {
    expect(getPublishedHtmlPreviewUrl("outputs/app-dist/about.html", siteUrl)).toBe(
      `${siteUrl}/about.html`,
    );
    expect(getPublishedHtmlPreviewUrl("outputs/app-dist/blog/index.html", siteUrl)).toBe(
      `${siteUrl}/blog/`,
    );
  });
});
