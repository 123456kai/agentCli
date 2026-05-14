import type { Core, EventObject } from "cytoscape";

export type OpenFileHandler = (path: string, line?: number) => void;
export type ExpandHandler = (nodeId: string) => void;
export type SelectHandler = (nodeId: string) => void;

export function setupGraphInteractions(
  cy: Core,
  onOpenFile: OpenFileHandler,
  onExpand: ExpandHandler,
  onSelect: SelectHandler,
): () => void {
  const openNode = (evt: EventObject) => {
    const node = evt.target;
    const path = String(node.data("path") ?? "");
    const line = Number(node.data("line") ?? 0);
    if (path) onOpenFile(path, line > 0 ? line : undefined);
  };

  const expandNode = (evt: EventObject) => {
    const node = evt.target;
    if (node.data("kind") !== "external") {
      onExpand(String(node.data("id")));
    }
  };

  const selectNode = (evt: EventObject) => {
    onSelect(String(evt.target.data("id")));
  };

  cy.on("dbltap", "node", openNode);
  cy.on("cxttap", "node", expandNode);
  cy.on("tap", "node", selectNode);

  return () => {
    cy.off("dbltap", "node", openNode);
    cy.off("cxttap", "node", expandNode);
    cy.off("tap", "node", selectNode);
  };
}
