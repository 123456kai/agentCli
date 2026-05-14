import type { StylesheetJson } from "cytoscape";

export const CALL_GRAPH_STYLES: StylesheetJson = [
  {
    selector: "node",
    style: {
      "background-color": "#4a7d2d",
      label: "data(label)",
      "font-size": "11px",
      color: "#d8dee9",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 6,
      width: 16,
      height: 16,
      "border-width": 1,
      "border-color": "#263238",
      shape: "round-rectangle",
    },
  },
  {
    selector: "node[kind='method']",
    style: { "background-color": "#2d6da4", "border-color": "#1a3a5c" },
  },
  {
    selector: "node[kind='class']",
    style: { "background-color": "#8b6d2d", "border-color": "#4a3d1a" },
  },
  {
    selector: "node[kind='external']",
    style: {
      "background-color": "#6d2d6d",
      "border-color": "#3d1a3d",
      shape: "ellipse",
      width: 12,
      height: 12,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#f0c674",
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#596275",
      "target-arrow-color": "#596275",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
  {
    selector: "edge[?is_cycle]",
    style: {
      "line-style": "dashed",
      "line-color": "#d08770",
      "target-arrow-color": "#d08770",
    },
  },
];
