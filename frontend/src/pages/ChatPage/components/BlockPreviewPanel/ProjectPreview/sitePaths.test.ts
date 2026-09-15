import { describe, expect, it } from "vite-plus/test";
import {
  SITE_VIRTUAL_DIST,
  SITE_VIRTUAL_OUTPUTS,
  isOutputsRootHtmlPath,
  isPublishableSitePath,
  isSiteDistPath,
  resolvePublishSource,
} from "./sitePaths";

describe("isSiteDistPath", () => {
  it("matches app-dist directory and children", () => {
    expect(isSiteDistPath("outputs/app-dist")).toBe(true);
    expect(isSiteDistPath("outputs/app-dist/index.html")).toBe(true);
    expect(isSiteDistPath("/mnt/user-data/outputs/app-dist/about.html")).toBe(true);
  });

  it("rejects outputs root html", () => {
    expect(isSiteDistPath("outputs/index.html")).toBe(false);
    expect(isSiteDistPath("outputs")).toBe(false);
  });
});

describe("isOutputsRootHtmlPath", () => {
  it("matches html files directly under outputs", () => {
    expect(isOutputsRootHtmlPath("outputs/index.html")).toBe(true);
    expect(isOutputsRootHtmlPath("/mnt/user-data/outputs/about.html")).toBe(true);
  });

  it("rejects nested html, app-dist, and non-html", () => {
    expect(isOutputsRootHtmlPath("outputs/blog/index.html")).toBe(false);
    expect(isOutputsRootHtmlPath("outputs/app-dist/index.html")).toBe(false);
    expect(isOutputsRootHtmlPath("outputs/style.css")).toBe(false);
  });
});

describe("isPublishableSitePath", () => {
  it("accepts app-dist, outputs root, and root html", () => {
    expect(isPublishableSitePath("outputs")).toBe(true);
    expect(isPublishableSitePath("outputs/index.html")).toBe(true);
    expect(isPublishableSitePath("outputs/app-dist/index.html")).toBe(true);
  });

  it("rejects workspace html", () => {
    expect(isPublishableSitePath("workspace/index.html")).toBe(false);
  });
});

describe("resolvePublishSource", () => {
  it("prefers app-dist when present", () => {
    expect(resolvePublishSource({ hasAppDist: true, hasOutputsIndex: true })).toBe(
      SITE_VIRTUAL_DIST,
    );
  });

  it("falls back to outputs when only index.html exists", () => {
    expect(resolvePublishSource({ hasAppDist: false, hasOutputsIndex: true })).toBe(
      SITE_VIRTUAL_OUTPUTS,
    );
  });

  it("keeps app-dist as the default when neither layout is detected", () => {
    expect(resolvePublishSource({ hasAppDist: false, hasOutputsIndex: false })).toBe(
      SITE_VIRTUAL_DIST,
    );
  });
});
