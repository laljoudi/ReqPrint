// A centered dialog over a dimmed page. The codebase had no modal primitive, so
// this is the minimal one: a titled panel, Escape to close, focus kept inside
// while it is open and handed back when it closes. `closable={false}` locks it
// (clicking outside and Escape do nothing) - used while a push is in flight, when
// closing would hide the result. Flat like the rest of the app: a border, no shadow.
import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Modal({ title, children, onClose, closable = true, wide = false }) {
  const titleId = useId();
  const panelRef = useRef(null);
  // Latest values for the key handler, which is registered once.
  const live = useRef({ onClose, closable });
  live.current = { onClose, closable };

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const panel = panelRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    (panel.querySelector("[data-autofocus]") || panel).focus();

    function onKeyDown(event) {
      if (event.key === "Escape" && live.current.closable) {
        event.stopPropagation();
        live.current.onClose?.();
        return;
      }
      if (event.key !== "Tab") return;
      const items = [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, []);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && closable) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`w-full ${wide ? "max-w-[520px]" : "max-w-[440px]"} max-h-[calc(100vh-2rem)] overflow-y-auto rounded-[18px] border border-border bg-panel p-6 outline-none`}
      >
        <h2 id={titleId} className="font-display font-bold text-[19px] tracking-tight text-ink m-0 mb-3">
          {title}
        </h2>
        {children}
      </div>
    </div>,
    document.body,
  );
}
