import { useState, useEffect, useCallback } from "react";
import { fetchConfig, fetchDefaults } from "../lib/api";
import type { ConfigResult, DefaultsResult } from "../lib/api";
import type { ConfigTree } from "../lib/types";

interface UseConfigReturn {
  config: ConfigTree;
  warnings: string[];
  updateConfig: (newConfig: ConfigTree) => void;
  resetConfig: (defaults?: ConfigTree) => void;
}

export function useConfig(): UseConfigReturn {
  const [config, setConfig] = useState<ConfigTree>({});
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

  const updateConfig = useCallback((newConfig: ConfigTree) => {
    setConfig(newConfig);
  }, []);

  const resetConfig = useCallback(async (defaults?: ConfigTree) => {
    if (defaults) {
      setConfig(defaults);
    } else {
      const result: DefaultsResult = await fetchDefaults();
      setConfig(result.defaults);
    }
  }, []);

  return { config, warnings, updateConfig, resetConfig };
}
