import { useEffect, useRef, useState } from "react";
import type { Storyline, StorylineNode } from "../components/coderead/types";

type EnhanceEvent =
  | { type: "enhancement_start"; storyline_id: string; total_nodes: number }
  | {
      type: "node_enhanced";
      node: {
        graph_node_id: string;
        order: number;
        summary: string;
        design_notes: string;
        warnings: string | null;
        next_teaser: string | null;
        error?: string;
      };
    }
  | { type: "enhancement_complete"; storyline_id: string };

type EnhancementState = {
  enhancing: boolean;
  enhancedCount: number;
  totalNodes: number;
  complete: boolean;
};

export function useSSEEnhancement(
  storylineId: string | null,
  onNodeEnhanced?: (graphNodeId: string, enhancement: {
    summary: string;
    design_notes: string;
    warnings: string | null;
    next_teaser: string | null;
  }) => void,
): EnhancementState {
  const [state, setState] = useState<EnhancementState>({
    enhancing: false,
    enhancedCount: 0,
    totalNodes: 0,
    complete: false,
  });
  const onNodeEnhancedRef = useRef(onNodeEnhanced);
  onNodeEnhancedRef.current = onNodeEnhanced;

  useEffect(() => {
    if (!storylineId) return;

    let cancelled = false;
    const url = `/api/storylines/${encodeURIComponent(storylineId)}/enhance`;

    const source = new EventSource(url);

    source.onmessage = (event: MessageEvent) => {
      if (cancelled) return;
      try {
        const data = JSON.parse(event.data) as EnhanceEvent;

        if (data.type === "enhancement_start") {
          setState({
            enhancing: true,
            enhancedCount: 0,
            totalNodes: data.total_nodes,
            complete: false,
          });
        } else if (data.type === "node_enhanced") {
          setState((prev) => ({
            ...prev,
            enhancedCount: prev.enhancedCount + 1,
          }));
          onNodeEnhancedRef.current?.(data.node.graph_node_id, {
            summary: data.node.summary,
            design_notes: data.node.design_notes,
            warnings: data.node.warnings,
            next_teaser: data.node.next_teaser,
          });
        } else if (data.type === "enhancement_complete") {
          setState((prev) => ({
            ...prev,
            enhancing: false,
            complete: true,
          }));
          source.close();
        }
      } catch {
        // Ignore parse errors for non-JSON lines (SSE comments, etc.)
      }
    };

    source.onerror = () => {
      if (!cancelled) {
        setState((prev) => ({
          ...prev,
          enhancing: false,
          complete: true,
        }));
      }
      source.close();
    };

    return () => {
      cancelled = true;
      source.close();
    };
  }, [storylineId]);

  return state;
}

/** Apply enhanced content to a storyline's nodes list. */
export function applyEnhancement(
  storylines: Storyline[],
  storylineId: string,
  graphNodeId: string,
  enhancement: {
    summary: string;
    design_notes: string;
    warnings: string | null;
    next_teaser: string | null;
  },
): Storyline[] {
  return storylines.map((s) => {
    if (s.id !== storylineId) return s;
    return {
      ...s,
      nodes: s.nodes.map((n) => {
        if (n.graph_node_id !== graphNodeId) return n;
        return {
          ...n,
          summary: enhancement.summary,
          design_notes: enhancement.design_notes,
          warnings: enhancement.warnings,
          next_teaser: enhancement.next_teaser,
        };
      }),
    };
  });
}
