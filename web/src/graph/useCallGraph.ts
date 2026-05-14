import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import cytoscape from "cytoscape";
import type { Core, ElementDefinition } from "cytoscape";
import dagre from "cytoscape-dagre";

import { fetchGraphExpand, fetchGraphNode, fetchGraphSkeleton } from "../api/client";
import { setupGraphInteractions } from "./interactions";
import { CALL_GRAPH_STYLES } from "./styles";
import type { GraphEdgeData, GraphNodeData, NodeDetailData } from "./types";

cytoscape.use(dagre);

export type CallGraphState = {
  isLoading: boolean;
  error: string | null;
  warning: string | null;
  skippedFiles: string[];
  nodeCount: number;
  edgeCount: number;
  selectedNode: NodeDetailData | null;
};

function toElements(nodes: GraphNodeData[], edges: GraphEdgeData[]): ElementDefinition[] {
  return [
    ...nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        path: node.path,
        line: node.line,
        kind: node.kind,
        degree: node.degree,
      },
    })),
    ...edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        relation: edge.relation,
        is_cycle: edge.is_cycle,
      },
    })),
  ];
}

function runLayout(cy: Core): void {
  cy.layout({
    name: "dagre",
    rankDir: "TB",
    spacingFactor: 1.25,
    animate: true,
    animationDuration: 250,
  } as cytoscape.LayoutOptions).run();
}

export function useCallGraph(
  containerRef: RefObject<HTMLDivElement | null>,
  onOpenFile: (path: string, line?: number) => void,
) {
  const cyRef = useRef<Core | null>(null);
  const onOpenFileRef = useRef(onOpenFile);
  const [state, setState] = useState<CallGraphState>({
    isLoading: true,
    error: null,
    warning: null,
    skippedFiles: [],
    nodeCount: 0,
    edgeCount: 0,
    selectedNode: null,
  });

  useEffect(() => {
    onOpenFileRef.current = onOpenFile;
  }, [onOpenFile]);

  const loadSkeleton = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    const controller = new AbortController();
    try {
      const data = await fetchGraphSkeleton(controller.signal);
      const cy = cyRef.current;
      if (!cy) return;

      cy.elements().remove();
      cy.add(toElements(data.nodes, data.edges));
      runLayout(cy);
      cy.fit(undefined, 24);

      setState((current) => ({
        ...current,
        isLoading: false,
        warning: data.warning ?? null,
        skippedFiles: data.skipped_files,
        nodeCount: data.nodes.length,
        edgeCount: data.edges.length,
        selectedNode: null,
      }));
    } catch (err) {
      setState((current) => ({
        ...current,
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to load graph",
      }));
    }
  }, []);

  const expandNode = useCallback(async (nodeId: string) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);
    try {
      const data = await fetchGraphExpand(nodeId, 3, controller.signal);
      window.clearTimeout(timeoutId);

      const cy = cyRef.current;
      if (!cy) return;

      cy.add(
        toElements(
          data.nodes.filter((node) => cy.getElementById(node.id).empty()),
          data.edges.filter((edge) => cy.getElementById(edge.id).empty()),
        ),
      );
      runLayout(cy);
      setState((current) => ({
        ...current,
        error: null,
        nodeCount: cy.nodes().length,
        edgeCount: cy.edges().length,
      }));
    } catch (err) {
      window.clearTimeout(timeoutId);
      const message =
        err instanceof DOMException && err.name === "AbortError"
          ? "Expand timeout. Please retry."
          : err instanceof Error
            ? err.message
            : "Failed to expand node";
      setState((current) => ({ ...current, error: message }));
    }
  }, []);

  const selectNode = useCallback(async (nodeId: string) => {
    try {
      const detail = await fetchGraphNode(nodeId);
      setState((current) => ({ ...current, selectedNode: detail, error: null }));
    } catch (err) {
      setState((current) => ({
        ...current,
        error: err instanceof Error ? err.message : "Failed to load node detail",
      }));
    }
  }, []);

  const fit = useCallback(() => {
    cyRef.current?.fit(undefined, 24);
  }, []);

  const openFileFromGraph = useCallback((path: string, line?: number) => {
    onOpenFileRef.current(path, line);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CALL_GRAPH_STYLES,
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 3,
    });
    cyRef.current = cy;
    const cleanupInteractions = setupGraphInteractions(cy, openFileFromGraph, expandNode, selectNode);
    loadSkeleton();

    return () => {
      cleanupInteractions();
      cy.destroy();
      cyRef.current = null;
    };
  }, [containerRef, expandNode, loadSkeleton, openFileFromGraph, selectNode]);

  return { state, loadSkeleton, expandNode, fit };
}
