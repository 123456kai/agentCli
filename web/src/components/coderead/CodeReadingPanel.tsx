import { useCallback, useEffect, useState } from "react";

import type { Storyline, ReadingState } from "./types";
import { fetchStorylines } from "../../api/client";
import { StorylineDiscovery } from "./StorylineDiscovery";
import { StorylineReader } from "./StorylineReader";
import { StorylineComplete } from "./StorylineComplete";

type CodeReadingPanelProps = {
  onOpenFile: (path: string, startLine: number, endLine: number) => void;
};

export function CodeReadingPanel({ onOpenFile }: CodeReadingPanelProps) {
  const [viewState, setViewState] = useState<ReadingState>("discovery");
  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [activeStoryline, setActiveStoryline] = useState<Storyline | null>(null);
  const [currentNodeIndex, setCurrentNodeIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const data = await fetchStorylines(controller.signal);
        if (!cancelled) {
          setStorylines(data.storylines);
          setError(null);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === "AbortError")) {
          setError("加载主线失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; controller.abort(); };
  }, []);

  const startReading = useCallback((storyline: Storyline) => {
    setActiveStoryline(storyline);
    setCurrentNodeIndex(0);
    setViewState("reading");
  }, []);

  const advanceNode = useCallback(() => {
    if (!activeStoryline) return;
    const nextIdx = currentNodeIndex + 1;
    if (nextIdx >= activeStoryline.nodes.length) {
      setViewState("complete");
    } else {
      setCurrentNodeIndex(nextIdx);
    }
  }, [activeStoryline, currentNodeIndex]);

  const previousNode = useCallback(() => {
    setCurrentNodeIndex((i) => Math.max(0, i - 1));
  }, []);

  const goToNode = useCallback((index: number) => {
    if (activeStoryline && index >= 0 && index < activeStoryline.nodes.length) {
      setCurrentNodeIndex(index);
    }
  }, [activeStoryline]);

  const backToDiscovery = useCallback(() => {
    setViewState("discovery");
    setActiveStoryline(null);
    setCurrentNodeIndex(0);
  }, []);

  const startNewStoryline = useCallback(() => {
    setViewState("discovery");
    setActiveStoryline(null);
    setCurrentNodeIndex(0);
  }, []);

  if (viewState === "discovery") {
    return (
      <StorylineDiscovery
        storylines={storylines}
        loading={loading}
        error={error}
        onSelect={startReading}
        onRefresh={() => {
          setLoading(true);
          setError(null);
          fetchStorylines().then((d) => {
            setStorylines(d.storylines);
            setLoading(false);
          }).catch(() => {
            setError("刷新失败");
            setLoading(false);
          });
        }}
      />
    );
  }

  if (viewState === "reading" && activeStoryline) {
    const currentNode = activeStoryline.nodes[currentNodeIndex];
    return (
      <StorylineReader
        storyline={activeStoryline}
        currentNode={currentNode}
        currentNodeIndex={currentNodeIndex}
        totalNodes={activeStoryline.nodes.length}
        onAdvance={advanceNode}
        onPrevious={previousNode}
        onGoToNode={goToNode}
        onExit={backToDiscovery}
        onOpenFile={onOpenFile}
      />
    );
  }

  if (viewState === "complete" && activeStoryline) {
    return (
      <StorylineComplete
        storyline={activeStoryline}
        onNewStoryline={startNewStoryline}
        onReplay={() => {
          setCurrentNodeIndex(0);
          setViewState("reading");
        }}
      />
    );
  }

  return null;
}
