import { describe, expect, it } from "vite-plus/test";
import {
  SITE_DIST_DIR,
  SITE_ENTRY_PATH,
  isSiteDistPath,
  outputsTreeHasAppDist,
  toWorkspaceRelativePath,
} from "./utils";

describe("toWorkspaceRelativePath", () => {
  it("strips the user-data virtual prefix", () => {
    expect(toWorkspaceRelativePath("/mnt/user-data/outputs/report.md")).toBe("outputs/report.md");
  });

  it("strips a leading slash on session-relative paths", () => {
    expect(toWorkspaceRelativePath("/outputs/app-dist/index.html")).toBe("outputs/app-dist/index.html");
  });
});

describe("isSiteDistPath", () => {
  it("matches the app-dist directory and its files", () => {
    expect(isSiteDistPath(SITE_DIST_DIR)).toBe(true);
    expect(isSiteDistPath(SITE_ENTRY_PATH)).toBe(true);
    expect(isSiteDistPath("/mnt/user-data/outputs/app-dist/assets/app.js")).toBe(true);
  });

  it("rejects markdown and other outputs", () => {
    expect(isSiteDistPath("outputs/report.md")).toBe(false);
    expect(isSiteDistPath("/mnt/user-data/outputs/notes.md")).toBe(false);
    expect(isSiteDistPath("outputs/app-dist-backup/index.html")).toBe(false);
    expect(isSiteDistPath(undefined)).toBe(false);
  });
});

describe("outputsTreeHasAppDist", () => {
  it("returns true when outputs lists an app-dist directory", () => {
    expect(
      outputsTreeHasAppDist([
        { title: "report.md", path: "outputs/report.md", nodeType: "file" },
        { title: "app-dist", path: SITE_DIST_DIR, nodeType: "dir", hasChildren: true },
      ]),
    ).toBe(true);
  });

  it("returns false for document-only outputs", () => {
    expect(
      outputsTreeHasAppDist([{ title: "report.md", path: "outputs/report.md", nodeType: "file" }]),
    ).toBe(false);
  });
});
