import { useState, useCallback, useRef, useEffect } from "react";
import { fetchPreview } from "../lib/api";
import type { PreviewResult } from "../lib/api";

interface UsePreviewReturn {
  result: PreviewResult | null;
  loading: boolean;
  error: string | null;
  requestPreview: (fileId: string, machineType: "laser" | "impact", config?: Record<string, any>) => void;
}

export function usePreview(debounceMs = 300): UsePreviewReturn {
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const requestPreview = useCallback(
    (fileId: string, machineType: "laser" | "impact", config?: Record<string, any>) => {
      // Cancel previous request
      if (abortRef.current) {
        abortRef.current.abort();
      }

      // Debounce
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      timerRef.current = setTimeout(async () => {
        setLoading(true);
        setError(null);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
          const data = await fetchPreview(fileId, machineType, config, controller.signal);
          if (!controller.signal.aborted) {
            setResult(data);
          }
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          if (!controller.signal.aborted) {
            setError(msg);
          }
        } finally {
          setLoading(false);
        }
      }, debounceMs);
    },
    [debounceMs],
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  return { result, loading, error, requestPreview };
}
