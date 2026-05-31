import { renderRepoStructureTree } from "../components/RepoStructureTree";
import { renderZreadRepoStructureArguments } from "../components/ZreadRepoStructureArguments";
import { renderZreadReadFileResult } from "../components/ZreadReadFileResult";
import { ZreadIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

const zreadIcon = renderIcon(ZreadIcon);

export const zreadRenderers: ToolRendererRegistry[string] = {
  get_repo_structure: {
    icon: zreadIcon,
    renderArguments: renderZreadRepoStructureArguments,
    renderResult: ctx => renderRepoStructureTree(ctx) ?? null,
  },
  read_file: {
    icon: zreadIcon,
    renderResult: ctx => renderZreadReadFileResult(ctx) ?? null,
  },
};
