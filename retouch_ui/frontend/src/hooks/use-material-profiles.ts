/** Хук для загрузки и кэширования MATERIAL_PROFILES.
 * Вызывает GET /api/material/profiles один раз при монтировании.
 */

import { useState, useEffect } from "react";
import { fetchMaterialProfiles } from "../lib/api";
import type { MaterialProfile } from "../lib/types";

interface UseMaterialProfilesReturn {
  profiles: Record<string, MaterialProfile>;
  loading: boolean;
  error: string | null;
}

let _cachedProfiles: Record<string, MaterialProfile> | null = null;

export function useMaterialProfiles(): UseMaterialProfilesReturn {
  const [profiles, setProfiles] = useState<Record<string, MaterialProfile>>(_cachedProfiles || {});
  const [loading, setLoading] = useState(!_cachedProfiles);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cachedProfiles) return;

    fetchMaterialProfiles()
      .then((data) => {
        _cachedProfiles = data.profiles;
        setProfiles(data.profiles);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Ошибка загрузки профилей");
        setLoading(false);
      });
  }, []);

  return { profiles, loading, error };
}
