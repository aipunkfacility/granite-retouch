import { useState, useCallback, useRef, useEffect } from "react";
import { fetchPreview } from "../lib/api";
import type { PreviewResult } from "../lib/api";
import type { MachineType, ConfigTree, ProfileType } from "../lib/types";
import type { FaceOvalParams } from "../lib/face-oval-geometry";

interface UsePreviewReturn {
  result: PreviewResult | null;
  loading: boolean;
  error: string | null;
  requestPreview: (
    fileId: string,
    machineType: MachineType,
    config?: ConfigTree,
    faceOval?: FaceOvalParams | null,
    profile?: ProfileType,
  ) => void;
}

export function usePreview(debounceMs = 300): UsePreviewReturn {
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // D.8.3: Version counter — protects against race conditions where
  // an older (slower) request resolves after a newer (faster) one.
  const versionRef = useRef(0);

  const requestPreview = useCallback(
    (
      fileId: string,
      machineType: MachineType,
      config?: ConfigTree,
      faceOval?: FaceOvalParams | null,
      profile?: ProfileType,
    ) => {
      // Cancel previous request
      if (abortRef.current) {
        abortRef.current.abort();
      }

      // Increment version — only the latest request can update state
      const thisVersion = ++versionRef.current;

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
          const data = await fetchPreview(
            fileId,
            machineType,
            config,
            controller.signal,
            faceOval,
            true,  // full_steps
            profile,
          );
          // D.8.3: Only accept result if this is still the latest request
          if (!controller.signal.aborted && versionRef.current === thisVersion) {
            setResult(data);
          }
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e);
          if (!controller.signal.aborted && versionRef.current === thisVersion) {
            setError(msg);
          }
        } finally {
          // Only clear loading if this is the latest request
          if (versionRef.current === thisVersion) {
            setLoading(false);
          }
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
