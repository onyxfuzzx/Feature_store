import React, { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

export function Modal({ isOpen = true, title, onClose, children, maxWidth = "max-w-lg" }) {
  const dialog = useRef(null), close = useRef(onClose), titleId = useId();
  close.current = onClose;
  useEffect(() => {
    if (!isOpen || !dialog.current) return;
    const element = dialog.current, previous = document.activeElement, overflow = document.body.style.overflow;
    element.showModal(); document.body.style.overflow = "hidden";
    return () => { element.close(); document.body.style.overflow = overflow; if (previous?.isConnected) previous.focus(); };
  }, [isOpen]);
  if (!isOpen) return null;
  return <dialog ref={dialog} aria-labelledby={titleId} aria-modal="true" tabIndex="-1"
    onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const controls = [...dialog.current.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')]
        .filter((element) => element.tabIndex >= 0 && element.getClientRects().length > 0);
      const first = controls[0], last = controls[controls.length - 1], active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialog.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (active === last || active === dialog.current)) { event.preventDefault(); first?.focus(); }
    }}
    onCancel={(event) => { event.preventDefault(); close.current(); }}
    onClick={(event) => { if (event.target === dialog.current) { const box = dialog.current.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close.current(); } }}
    className={`m-auto w-[calc(100%-2rem)] ${maxWidth} max-h-[90vh] overflow-y-auto bg-zinc-900 text-zinc-100 border border-zinc-800 rounded-xl shadow-2xl p-6 backdrop:bg-black/70`}>
    <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-5">
      <h2 id={titleId} className="text-base font-semibold">{title}</h2>
      <button type="button" onClick={onClose} className="p-1 rounded hover:bg-zinc-800" aria-label="Close modal"><X className="w-4 h-4" /></button>
    </div>
    {children}
  </dialog>;
}
