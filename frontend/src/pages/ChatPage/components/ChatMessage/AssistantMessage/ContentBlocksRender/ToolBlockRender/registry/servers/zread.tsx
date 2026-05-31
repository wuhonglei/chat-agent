import { ApartmentOutlined } from "@ant-design/icons";

import { renderRepoStructureTree } from "../components/RepoStructureTree";
import { ICON_CLASS_NAME } from "../icons";
import type { ToolRendererRegistry } from "../types";

const repoStructureIcon = <ApartmentOutlined className={ICON_CLASS_NAME} />;

export const zreadRenderers: ToolRendererRegistry[string] = {
  get_repo_structure: {
    icon: repoStructureIcon,
    renderResult: ctx => renderRepoStructureTree(ctx) ?? null,
  },
};
