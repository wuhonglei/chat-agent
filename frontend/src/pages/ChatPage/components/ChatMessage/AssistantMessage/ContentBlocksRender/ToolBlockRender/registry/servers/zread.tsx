import { renderRepoStructureTree } from "../components/RepoStructureTree";
import { renderZreadRepoStructureArguments } from "../components/ZreadRepoStructureArguments";
import { renderZreadReadFileArguments } from "../components/ZreadReadFileArguments";
import { renderZreadReadFileResult } from "../components/ZreadReadFileResult";
import { renderZreadSearchDocArguments } from "../components/ZreadSearchDocArguments";
import { renderZreadSearchDocResult } from "../components/ZreadSearchDocResult";
import type { ToolRendererRegistry } from "../types";

export const zreadRenderers: ToolRendererRegistry[string] = {
  get_repo_structure: {
    renderArguments: renderZreadRepoStructureArguments,
    renderResult: ctx => renderRepoStructureTree(ctx) ?? null,
  },
  read_file: {
    renderArguments: ctx => renderZreadReadFileArguments(ctx) ?? null,
    renderResult: ctx => renderZreadReadFileResult(ctx) ?? null,
  },
  search_doc: {
    renderArguments: ctx => renderZreadSearchDocArguments(ctx) ?? null,
    renderResult: ctx => renderZreadSearchDocResult(ctx) ?? null,
  },
};
