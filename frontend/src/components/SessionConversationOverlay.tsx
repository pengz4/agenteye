import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { fetchSessionTurns } from "../api";
import type { AgentTask, SessionTurnsPage, Turn } from "../types";

interface SessionConversationOverlayProps {
  task: AgentTask;
  title: string;
  onClose: () => void;
}

interface CachedPage {
  response: SessionTurnsPage;
  expiresAt: number;
}

const PAGE_SIZE = 10;
const CACHE_TTL_MS = 60_000;
const MAX_CACHED_PAGES = 24;
const pageCache = new Map<string, CachedPage>();
const inFlightPages = new Map<string, Promise<SessionTurnsPage>>();

function clampedPosition(x: number, y: number) {
  const width = Math.min(540, window.innerWidth - 24);
  const height = Math.min(620, window.innerHeight - 24);
  return {
    x: Math.min(
      Math.max(12, x),
      Math.max(12, window.innerWidth - width - 12),
    ),
    y: Math.min(
      Math.max(12, y),
      Math.max(12, window.innerHeight - height - 12),
    ),
  };
}

async function cachedPage(
  sessionId: string,
  before?: number,
): Promise<SessionTurnsPage> {
  const key = `${sessionId}:${before ?? "latest"}:${PAGE_SIZE}`;
  const cached = pageCache.get(key);
  if (cached && cached.expiresAt > Date.now()) return cached.response;

  const inFlight = inFlightPages.get(key);
  if (inFlight) return inFlight;
  const request = fetchSessionTurns(sessionId, { before, limit: PAGE_SIZE });
  inFlightPages.set(key, request);
  const response = await request.finally(() => inFlightPages.delete(key));
  if (pageCache.size >= MAX_CACHED_PAGES) {
    const oldestKey = pageCache.keys().next().value;
    if (oldestKey) pageCache.delete(oldestKey);
  }
  pageCache.set(key, { response, expiresAt: Date.now() + CACHE_TTL_MS });
  return response;
}

function identityLabel(task: AgentTask): string {
  const project = task.repository?.split("/").pop() || task.cwd.split(/[\\/]/).pop() || "Unknown";
  const branch = task.branch ? ` · ${task.branch}` : "";
  const rawSessionId = task.session_id.replace(/^(cc:|scout:)/, "");
  const session = task.session_short_id || rawSessionId.slice(0, 6);
  return `${task.source} · ${project}${branch} · ${session}`;
}

export default function SessionConversationOverlay({
  task,
  title,
  onClose,
}: SessionConversationOverlayProps) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [hasEarlier, setHasEarlier] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState(() =>
    clampedPosition(window.innerWidth - 560, 82),
  );
  const drag = useRef<{ pointerX: number; pointerY: number; x: number; y: number } | null>(null);

  const loadPage = useCallback(async (before?: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await cachedPage(task.session_id, before);
      setTurns((current) => {
        const merged = before === undefined ? page.turns : [...page.turns, ...current];
        return merged.filter(
          (turn, index) =>
            merged.findIndex((candidate) => candidate.turn_index === turn.turn_index) === index,
        );
      });
      setHasEarlier(page.has_earlier);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Conversation unavailable");
    } finally {
      setLoading(false);
    }
  }, [task.session_id]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      if (!drag.current) return;
      setPosition(clampedPosition(
        drag.current.x + event.clientX - drag.current.pointerX,
        drag.current.y + event.clientY - drag.current.pointerY,
      ));
    };
    const handleUp = () => {
      drag.current = null;
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, []);

  useEffect(() => {
    const clampToViewport = () => {
      setPosition((current) => clampedPosition(current.x, current.y));
    };
    window.addEventListener("resize", clampToViewport);
    return () => window.removeEventListener("resize", clampToViewport);
  }, []);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      x: position.x,
      y: position.y,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const earliestTurn = turns.length > 0 ? Math.min(...turns.map((turn) => turn.turn_index)) : undefined;

  return (
    <section
      className="session-conversation-overlay"
      role="dialog"
      aria-label="Session conversation"
      aria-modal="false"
      style={{ left: position.x, top: position.y }}
    >
      <div
        className="session-conversation-handle"
        onPointerDown={startDrag}
        aria-label="Drag session conversation"
      >
        <div>
          <div className="session-conversation-kicker">Read-only session context</div>
          <h2>{title || "Session conversation"}</h2>
          <p>{identityLabel(task)}</p>
        </div>
        <button className="close-x" aria-label="Close session conversation" onClick={onClose}>
          ×
        </button>
      </div>

      <div className="session-conversation-body">
        {hasEarlier && !loading && earliestTurn !== undefined && (
          <button
            className="view-btn session-conversation-load"
            aria-label="Load earlier"
            onClick={() => void loadPage(earliestTurn)}
          >
            Load earlier
          </button>
        )}
        {loading && turns.length === 0 && (
          <div className="loading" role="status">Loading conversation…</div>
        )}
        {error && <div className="session-conversation-error" role="alert">{error}</div>}
        {!loading && !error && turns.length === 0 && (
          <div className="empty">No conversation turns are available for this session.</div>
        )}
        {turns.map((turn) => (
          <article className="session-conversation-turn" key={turn.turn_index}>
            <div className="session-conversation-index">Turn {turn.turn_index + 1}</div>
            {turn.user_message && (
              <div className="session-conversation-message user">
                <span>User</span>
                <p>{turn.user_message}</p>
              </div>
            )}
            {turn.assistant_response && (
              <div className="session-conversation-message assistant">
                <span>Assistant</span>
                <p>{turn.assistant_response}</p>
              </div>
            )}
            {!turn.assistant_response && turn.user_message && (
              <div className="session-conversation-message assistant is-missing">
                <span>Assistant</span>
                <p>Assistant response not recorded yet.</p>
              </div>
            )}
          </article>
        ))}
        {loading && turns.length > 0 && (
          <div className="loading session-conversation-loading" role="status">
            Loading earlier turns…
          </div>
        )}
      </div>
    </section>
  );
}
