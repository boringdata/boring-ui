import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  onClose: () => void;
  authError?: string | null;
  presentation?: "modal" | "inline";
}

function getManagedAuthBase(): string {
  return "/api/v1/chat/auth";
}

function normalizeLegacyAuthMessage(value: string): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const lower = raw.toLowerCase();
  if (
    lower.includes("please run /login")
    || lower.includes("run /login")
    || lower.includes("not logged in")
  ) {
    return "Authentication required. Use Login to Claude and complete browser sign-in.";
  }
  return raw;
}

export function EnvManager({
  onClose,
  authError = null,
  presentation = "modal",
}: Props) {
  const isInline = presentation === "inline";
  const [managedLoginUrl, setManagedLoginUrl] = useState("");
  const [managedStatus, setManagedStatus] = useState("");
  const [managedStatusError, setManagedStatusError] = useState(false);
  const [managedBusy, setManagedBusy] = useState(false);
  const [managedProviderLabel, setManagedProviderLabel] = useState("Chat provider");
  const [managedSupported, setManagedSupported] = useState(true);
  const statusPollRef = useRef<number | null>(null);

  async function loadManagedAuthMeta() {
    let supported = true;
    try {
      const resp = await fetch(`${getManagedAuthBase()}/meta`);
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) return { supported };

      const label = String(data.provider_label || "").trim();
      if (label) setManagedProviderLabel(label);
      if (data.managed_login_supported === false) {
        supported = false;
        setManagedSupported(false);
      }
    } catch {
      // Keep default values.
    }
    return { supported };
  }

  async function checkManagedAuthStatus(silent = false) {
    if (!managedSupported) return { loggedIn: false, activeSession: false };
    if (!silent) {
      setManagedBusy(true);
      setManagedStatus("");
      setManagedStatusError(false);
    }

    try {
      const resp = await fetch(`${getManagedAuthBase()}/status`);
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setManagedStatus("Unable to check Claude login status.");
        setManagedStatusError(true);
        return null;
      }

      const active = data?.active_login_session && typeof data.active_login_session === "object"
        ? data.active_login_session
        : null;
      const activeSession = Boolean(active);
      if (active) {
        const loginUrl = String(active?.url || "").trim();
        if (loginUrl) setManagedLoginUrl(loginUrl);
      }

      if (data.logged_in) {
        setManagedStatus(`${managedProviderLabel} login is active in this runtime.`);
        setManagedStatusError(false);
        window.setTimeout(() => onClose(), 400);
      } else {
        setManagedStatus(`${managedProviderLabel} is not logged in yet.`);
        setManagedStatusError(false);
      }

      return { loggedIn: Boolean(data.logged_in), activeSession };
    } catch {
      setManagedStatus("Unable to check chat login status.");
      setManagedStatusError(true);
      return null;
    } finally {
      setManagedBusy(false);
    }
  }

  function stopStatusPolling() {
    if (statusPollRef.current !== null) {
      window.clearInterval(statusPollRef.current);
      statusPollRef.current = null;
    }
  }

  function startStatusPolling() {
    stopStatusPolling();
    statusPollRef.current = window.setInterval(() => {
      checkManagedAuthStatus(true).catch(() => {});
    }, 3000);
  }

  async function startManagedClaudeLogin() {
    if (!managedSupported) return;

    setManagedBusy(true);
    setManagedStatus(`Starting ${managedProviderLabel} login...`);
    setManagedStatusError(false);
    setManagedLoginUrl("");

    try {
      const resp = await fetch(`${getManagedAuthBase()}/login-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        setManagedStatus(data?.message || "Unable to start managed login.");
        setManagedStatusError(true);
        return;
      }

      if (data?.already_logged_in || data?.logged_in) {
        stopStatusPolling();
        setManagedStatus(`${managedProviderLabel} login is already active in this runtime.`);
        setManagedStatusError(false);
        return;
      }

      if (!data?.url) {
        setManagedStatus(data?.message || "Unable to start managed login.");
        setManagedStatusError(true);
        return;
      }

      const loginUrl = String(data.url);
      setManagedLoginUrl(loginUrl);

      if (data?.running === false) {
        stopStatusPolling();
        if (data?.logged_in) {
          setManagedStatus(`${managedProviderLabel} login is active in this runtime.`);
          setManagedStatusError(false);
          window.setTimeout(() => onClose(), 400);
          return;
        }
        setManagedStatus(String(data?.message || "Claude login process exited before authentication completed."));
        setManagedStatusError(true);
        return;
      }

      const opened = window.open(loginUrl, "_blank", "noopener,noreferrer");
      startStatusPolling();
      setManagedStatus(
        opened
          ? "Complete sign-in in the browser tab. Status refreshes automatically."
          : "Popup blocked. Click Login to Claude again to open the sign-in tab.",
      );
      setManagedStatusError(false);
    } catch {
      setManagedStatus("Unable to start managed login.");
      setManagedStatusError(true);
    } finally {
      setManagedBusy(false);
    }
  }

  function openManagedLoginLink() {
    if (!managedLoginUrl) return;

    const opened = window.open(managedLoginUrl, "_blank", "noopener,noreferrer");
    if (!opened) {
      setManagedStatus("Popup blocked. Allow popups, then click Login to Claude again.");
      setManagedStatusError(false);
    }
  }

  useEffect(() => {
    (async () => {
      const meta = await loadManagedAuthMeta().catch(() => ({ supported: true }));
      const status = await checkManagedAuthStatus(true).catch(() => null);

      if (meta?.supported === false) return;
      if (Boolean(status?.activeSession)) startStatusPolling();
    })();

    return () => {
      stopStatusPolling();
    };
  }, []);

  const title = `Authenticate with ${managedProviderLabel}`;
  const authErrorMessage = normalizeLegacyAuthMessage(String(authError || "").trim());

  const panel = (
    <div
      className={`w-full max-w-lg ${isInline ? "max-h-none" : "max-h-[80vh]"} flex flex-col bg-cc-bg border border-cc-border rounded-[14px] shadow-2xl overflow-hidden`}
      onClick={(e) => {
        if (!isInline) e.stopPropagation();
      }}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-cc-border">
        <h2 className="text-sm font-semibold text-cc-fg">{title}</h2>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-md text-cc-muted hover:text-cc-fg hover:bg-cc-hover transition-colors cursor-pointer"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
            <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <div className="border border-cc-border rounded-[10px] overflow-hidden">
          <div className="px-3 py-3 space-y-2">
            {!managedSupported && (
              <div className="text-[11px] text-cc-muted">
                Managed login is not available for the current chat provider yet.
              </div>
            )}
            {authErrorMessage && (
              <div className="text-[11px] text-cc-error">
                {authErrorMessage}
              </div>
            )}
            <div className="text-[11px] text-cc-muted">
              {managedLoginUrl
                ? "Complete sign-in in the browser tab. Status refreshes automatically."
                : "Sign in to Claude to enable the chat assistant."}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (managedLoginUrl) {
                    openManagedLoginLink();
                    return;
                  }
                  startManagedClaudeLogin().catch(() => {});
                }}
                disabled={managedBusy || !managedSupported}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  managedBusy || !managedSupported
                    ? "bg-cc-hover text-cc-muted cursor-not-allowed"
                    : "bg-cc-primary hover:bg-cc-primary-hover text-white cursor-pointer"
                }`}
              >
                Login to Claude
              </button>
            </div>
            {managedStatus && (
              <div className={`text-[11px] ${managedStatusError ? "text-cc-error" : "text-cc-muted"}`}>
                {managedStatus}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (isInline) {
    return (
      <div className="h-full min-h-0 overflow-y-auto px-4 py-5 bg-cc-bg">
        <div className="mx-auto w-full max-w-lg">{panel}</div>
      </div>
    );
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      {panel}
    </div>,
    document.body,
  );
}
