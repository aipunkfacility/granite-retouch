import { useState, useEffect, useCallback } from "react";
import { fetchConfig, fetchDefaults } from "../lib/api";
import type { ConfigResult } from "../lib/api";

interface UseConfigReturn {
  config: Record<string, any>;
  warnings: string[];
  updateConfig: (newConfig: Record<string, any>) => void;
  resetConfig: (defaults?: Record<string, any>) => void;
}

export function useConfig(): UseConfigReturn {
  const [config, setConfig] = useState<Record<string, any>>({});
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    fetchConfig()
      .then((result: ConfigResult) => {
        setConfig(result.config);
        setWarnings(result.warnings);
      })
      .catch(() => {
        // Backend unavailable — use empty config
      });
  }, []);

  const updateConfig = useCallback((newConfig: Record<string, any>) => {
    setConfig(newConfig);
  }, []);

  const resetConfig = useCallback(async (defaults?: Record<string, any>) => {
    if (defaults) {
      setConfig(defaults);
    } else {
      const result = await fetchDefaults();
      setConfig(result.config);
      setWarnings(result.warnings);
    }
  }, []);

  return { config, warnings, updateConfig, resetConfig };
}
