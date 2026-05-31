import { ApartmentOutlined, FileTextOutlined } from "@ant-design/icons";

import { renderRepoStructureTree } from "../components/RepoStructureTree";
import { renderZreadRepoStructureArguments } from "../components/ZreadRepoStructureArguments";
import { renderZreadReadFileResult } from "../components/ZreadReadFileResult";
import { ICON_CLASS_NAME } from "../icons";
import type { ToolRendererRegistry } from "../types";

const repoStructureIcon = <ApartmentOutlined className={ICON_CLASS_NAME} />;
const readFileIcon = <FileTextOutlined className={ICON_CLASS_NAME} />;

export const zreadRenderers: ToolRendererRegistry[string] = {
  get_repo_structure: {
    icon: repoStructureIcon,
    renderArguments: renderZreadRepoStructureArguments,
    renderResult: ctx => renderRepoStructureTree(ctx) ?? null,
  },
  read_file: {
    icon: readFileIcon,
    renderResult: ctx => renderZreadReadFileResult(ctx) ?? null,
  },
};
