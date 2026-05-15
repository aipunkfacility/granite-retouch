import { useState, useEffect, useCallback } from "react";
import { fetchConfig, fetchDefaults } from "../lib/api";
import type { ConfigResult, DefaultsResult } from "../lib/api";
import type { ConfigTree } from "../lib/types";

interface UseConfigReturn {
  config: ConfigTree;
  warnings: string[];
  error: string | null;
  updateConfig: (newConfig: ConfigTree) => void;
  resetConfig: (defaults?: ConfigTree) => void;
}

export function useConfig(): UseConfigReturn {
  const [config, setConfig] = useState<ConfigTree>({});
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig()
      .then((result: ConfigResult) => {
        setConfig(result.config);
        setWarnings(result.warnings);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Ошибка загрузки конфигурации");
      });
  }, []);

  const updateConfig = useCallback((newConfig: ConfigTree) => {
    setConfig(newConfig);
  }, []);

  const resetConfig = useCallback(async (defaults?: ConfigTree) => {
    if (defaults) {
      setConfig(defaults);
    } else {
      try {
        const result: DefaultsResult = await fetchDefaults();
        setConfig(result.defaults);
      } catch (e) {
        console.error("Failed to fetch defaults:", e);
      }
    }
  }, []);

  return { config, warnings, error, updateConfig, resetConfig };
}
