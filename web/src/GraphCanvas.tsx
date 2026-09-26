import { useEffect, useRef } from "react";
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import Sigma from "sigma";
import { Focus, Maximize2, Minus, Plus } from "lucide-react";

// Domain-neutral graph mechanics shared by every canvas that renders a graphology Graph
// (the Imagined World graph, the Memory projection, or any future one). Domain modules own
// node/edge construction, color palettes, labels, and inspectors; this module owns Sigma's
// lifecycle, layout, camera, and selection highlighting only.

export function initialPosition(name: string, index: number, count: number): { x: number; y: number } {
  let hash = 2166136261;
  for (let i = 0; i < name.length; i += 1) hash = Math.imul(hash ^ name.charCodeAt(i), 16777619);
  const angle = (index / Math.max(count, 1)) * Math.PI * 2 + ((hash >>> 0) % 100) / 100;
  const radius = 4 + ((hash >>> 8) % 100) / 35;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

export function formatType(type: string): string {
  const spaced = type.replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.replace(/\b\w/g, (char) => char.toUpperCase());
}

// Runs force-directed layout, then sizes nodes by degree. A node flagged with the
// `emphasizedAttribute` (default "emphasized") keeps a fixed larger size instead — used by
// callers that want one anchor node (e.g. a primary identity) to stay visually prominent.
export function layoutGraph(graph: Graph, options: { emphasizedAttribute?: string } = {}): void {
  const emphasizedAttribute = options.emphasizedAttribute ?? "emphasized";
  if (graph.order > 1 && graph.size > 0) {
    forceAtlas2.assign(graph, { iterations: Math.min(160, 40 + graph.order * 2), settings: { gravity: 1.1, scalingRatio: 7, slowDown: 4 } });
  }
  graph.forEachNode((node) => {
    const emphasized = Boolean(graph.getNodeAttribute(node, emphasizedAttribute));
    graph.setNodeAttribute(node, "size", emphasized ? 19 : Math.min(14, 5.5 + Math.sqrt(graph.degree(node)) * 1.8));
  });
}

export function GraphCanvas({
  graph, selected, onSelect,
  highlightColor = "#d4caff", dimNodeColor = "#302e35",
  highlightEdgeColor = "#8074aa", dimEdgeColor = "#28272a",
}: {
  graph: Graph;
  selected: string | null;
  onSelect: (name: string | null) => void;
  highlightColor?: string;
  dimNodeColor?: string;
  highlightEdgeColor?: string;
  dimEdgeColor?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const renderer = useRef<Sigma | null>(null);
  const selectedRef = useRef<string | null>(selected);
  useEffect(() => {
    if (!container.current || graph.order === 0) return;
    const sigma = new Sigma(graph, container.current, {
      allowInvalidContainer: true,
      renderEdgeLabels: false,
      labelColor: { color: "#d9d5df" },
      labelFont: "DM Sans",
      labelSize: 12,
      labelDensity: .7,
      labelGridCellSize: 140,
      labelRenderedSizeThreshold: 9,
      defaultEdgeColor: "#35333a",
      defaultNodeColor: "#9484db",
      stagePadding: 50,
      nodeReducer: (node, data) => {
        const active = selectedRef.current;
        if (!active) return data;
        if (node === active) return { ...data, highlighted: true, zIndex: 2, size: data.size * 1.28, color: highlightColor };
        if (graph.areNeighbors(node, active)) return { ...data, zIndex: 1, size: data.size * 1.08 };
        return { ...data, color: dimNodeColor, label: "", zIndex: 0 };
      },
      edgeReducer: (edge, data) => {
        const active = selectedRef.current;
        if (!active) return data;
        const [source, target] = graph.extremities(edge);
        return source === active || target === active ? { ...data, color: highlightEdgeColor, size: 1.8, zIndex: 1 } : { ...data, color: dimEdgeColor, hidden: false, zIndex: 0 };
      },
    });
    sigma.on("clickNode", ({ node }) => onSelect(node));
    sigma.on("clickStage", () => onSelect(null));
    renderer.current = sigma;
    return () => { sigma.kill(); renderer.current = null; };
  }, [graph, onSelect, highlightColor, dimNodeColor, highlightEdgeColor, dimEdgeColor]);
  useEffect(() => {
    selectedRef.current = selected;
    renderer.current?.refresh();
    if (!selected || !renderer.current || !graph.hasNode(selected)) return;
    const display = renderer.current.getNodeDisplayData(selected);
    if (display) renderer.current.getCamera().animate({ x: display.x, y: display.y, ratio: .45 }, { duration: 350 });
  }, [selected, graph]);
  const zoom = (factor: number) => renderer.current?.getCamera().animatedZoom({ duration: 220, factor });
  const reset = () => renderer.current?.getCamera().animatedReset({ duration: 320 });
  return <>
    <div className="sigma-container" ref={container} />
    <div className="graph-controls" aria-label="Graph controls">
      <button onClick={() => zoom(1.4)} aria-label="Zoom in"><Plus size={15} /></button>
      <button onClick={() => zoom(.72)} aria-label="Zoom out"><Minus size={15} /></button>
      <button onClick={reset} aria-label="Fit graph"><Maximize2 size={14} /></button>
      {selected ? <button onClick={() => onSelect(null)} aria-label="Clear focus"><Focus size={14} /></button> : null}
    </div>
  </>;
}
