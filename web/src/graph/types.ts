export type GraphNodeData = {
  id: string;
  label: string;
  path: string;
  line: number;
  kind: "function" | "method" | "class" | "external";
  degree: number;
};

export type GraphEdgeData = {
  id: string;
  source: string;
  target: string;
  relation: "calls";
  is_cycle: boolean;
};

export type SkeletonData = {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  warning?: string | null;
  skipped_files: string[];
};

export type ExpandData = {
  root: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
};

export type NodeDetailData = {
  node: GraphNodeData | null;
  incoming: GraphEdgeData[];
  outgoing: GraphEdgeData[];
};
