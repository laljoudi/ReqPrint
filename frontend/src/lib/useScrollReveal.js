import { useEffect, useRef, useState } from "react";

// Flips `visible` to true once, the first time the element scrolls into
// view - used to trigger the fade/slide-in CSS transitions on the landing
// page sections. Does not re-trigger on scroll-out, so the page doesn't
// re-animate every time you scroll up and down past a section.
export function useScrollReveal(threshold = 0.15) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, visible };
}
