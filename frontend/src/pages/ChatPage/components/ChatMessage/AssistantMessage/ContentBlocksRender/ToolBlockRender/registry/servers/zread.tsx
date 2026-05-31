import { renderRepoStructureTree } from "../components/RepoStructureTree";
import { renderZreadRepoStructureArguments } from "../components/ZreadRepoStructureArguments";
import { renderZreadReadFileResult } from "../components/ZreadReadFileResult";
import type { ToolRendererRegistry } from "../types";

export const zreadRenderers: ToolRendererRegistry[string] = {
  get_repo_structure: {
    renderArguments: renderZreadRepoStructureArguments,
    renderResult: ctx => renderRepoStructureTree(ctx) ?? null,
  },
  read_file: {
    renderResult: ctx => renderZreadReadFileResult(ctx) ?? null,
  },
};
