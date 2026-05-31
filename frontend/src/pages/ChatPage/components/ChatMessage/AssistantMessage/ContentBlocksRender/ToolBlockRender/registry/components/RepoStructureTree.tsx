import { FileOutlined, FolderOutlined } from "@ant-design/icons";
import { Typography } from "antd";
import type { DataNode } from "antd/es/tree";
import Tree from "antd/es/tree";
import React, { useMemo } from "react";

import type { ToolRenderContext } from "../types";
import { parseRepoStructureContent } from "../utils/parseRepoStructure";

const TREE_HEIGHT = 320;

function getRepoLabel(ctx: ToolRenderContext): string | null {
  const args = ctx.toolUseBlock.argumentsJson;
  if (!args) {
    return null;
  }
  const repoName = args.repo_name ?? args.repo;
  if (typeof repoName !== "string" || !repoName.trim()) {
    return null;
  }
  const dirPath = args.dir_path ?? args.path;
  if (typeof dirPath === "string" && dirPath.trim() && dirPath !== "/") {
    return `${repoName}${dirPath.startsWith("/") ? "" : "/"}${dirPath}`;
  }
  return repoName;
}

function countNodes(nodes: DataNode[]): number {
  return nodes.reduce((total, node) => total + 1 + (node.children ? countNodes(node.children) : 0), 0);
}

function getDefaultExpandedKeys(nodes: DataNode[], maxDepth = 1, depth = 0): React.Key[] {
  if (depth >= maxDepth) {
    return [];
  }
  return nodes.flatMap(node => [
    node.key,
    ...(node.children ? getDefaultExpandedKeys(node.children, maxDepth, depth + 1) : []),
  ]);
}

export function renderRepoStructureTree(ctx: ToolRenderContext): React.ReactNode | null {
  const content = ctx.toolResultBlock?.content?.trim();
  if (!content) {
    return null;
  }

  const treeData = parseRepoStructureContent(content);
  if (!treeData?.length) {
    return null;
  }

  return <RepoStructureTreeView treeData={treeData} repoLabel={getRepoLabel(ctx)} />;
}

type RepoStructureTreeViewProps = {
  treeData: DataNode[];
  repoLabel: string | null;
};

const RepoStructureTreeView: React.FC<RepoStructureTreeViewProps> = ({ treeData, repoLabel }) => {
  const nodeCount = useMemo(() => countNodes(treeData), [treeData]);
  const defaultExpandedKeys = useMemo(() => getDefaultExpandedKeys(treeData), [treeData]);
  const expandAll = nodeCount <= 40;

  return (
    <div className="w-full rounded border border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) p-3">
      {repoLabel ? (
        <Typography.Text type="secondary" className="mb-2 block text-sm">
          {repoLabel}
        </Typography.Text>
      ) : null}
      <Tree
        blockNode
        showLine
        height={TREE_HEIGHT}
        treeData={treeData}
        defaultExpandAll={expandAll}
        defaultExpandedKeys={expandAll ? undefined : defaultExpandedKeys}
        titleRender={node => (
          <span className="inline-flex items-center gap-1.5 text-sm">
            {node.isLeaf ? (
              <FileOutlined className="text-(--ant-color-text-tertiary)" />
            ) : (
              <FolderOutlined className="text-(--ant-color-warning)" />
            )}
            <span>{typeof node.title === "function" ? node.key : node.title}</span>
          </span>
        )}
      />
    </div>
  );
};
