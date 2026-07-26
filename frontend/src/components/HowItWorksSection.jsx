// Landing page section: the 4-step workflow, told visually (short labels,
// no paragraphs) instead of describing it in prose.
import { useScrollReveal } from "../lib/useScrollReveal";

const STEPS = [
  { n: "1", title: "Project Idea", caption: "Describe it in plain language" },
  {
    n: "2",
    title: "Clarifying Questions",
    caption: "ReqPrint asks adaptive questions, each building on your last answer, until it has a complete picture.",
  },
  { n: "3", title: "Requirements Generation", caption: "Structured, numbered, complete" },
  { n: "4", title: "Export Word Document", caption: "Download and share instantly" },
];

function Step({ step, i, visible }) {
  return (
    <div
      className="flex-1 flex flex-col items-center text-center px-2 transition-all duration-700 ease-out"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(16px)",
        transitionDelay: `${i * 110}ms`,
      }}
    >
      <div className="w-11 h-11 rounded-full bg-accent/10 text-accent font-mono font-bold text-[15px] flex items-center justify-center mb-4">
        {step.n}
      </div>
      <div className="font-display font-bold text-[15px] text-ink leading-snug">{step.title}</div>
      <div className="text-[13px] text-hint mt-1.5">{step.caption}</div>
    </div>
  );
}

export default function HowItWorksSection() {
  const { ref, visible } = useScrollReveal();

  return (
    <section ref={ref} className="max-w-5xl mx-auto px-6 py-24 md:py-28">
      <div className="text-center mb-16">
        <div className="text-[11px] font-bold tracking-[0.09em] uppercase text-accent mb-3">
          How It Works
        </div>
        <h2 className="font-display font-extrabold text-3xl md:text-4xl tracking-tight text-ink">
          From idea to requirements document
        </h2>
      </div>

      <div className="relative flex flex-col md:flex-row items-stretch gap-10 md:gap-0">
        <div
          className="hidden md:block absolute left-[10%] right-[10%] top-[22px] h-px bg-border transition-transform duration-700 ease-out"
          style={{ transform: visible ? "scaleX(1)" : "scaleX(0)", transformOrigin: "left" }}
        />
        {STEPS.map((step, i) => (
          <Step key={step.n} step={step} i={i} visible={visible} />
        ))}
      </div>
    </section>
  );
}
