import { useEffect, useState } from "react";
import { fetchSessionCounts } from "../api";
import type { SessionCounts } from "../types";

const SESSION_COUNTS_POLL_MS = 15_000;
const EMPTY_COUNTS: SessionCounts = { active: 0, previous: 0 };

export function useSessionCounts(activeIds: string[], enabled: boolean) {
  const [counts, setCounts] = useState<SessionCounts>(EMPTY_COUNTS);
  const activeKey = [...activeIds].sort().join(",");

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const refresh = () => {
      fetchSessionCounts(activeIds)
        .then((next) => {
          if (!cancelled) setCounts(next);
        })
        .catch(() => {});
    };
    refresh();
    const timer = window.setInterval(refresh, SESSION_COUNTS_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  // The sorted key avoids refetching when only object insertion order changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, enabled]);

  return counts;
}
