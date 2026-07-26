// Landing page section: "why", not "what" - the reasoning behind each major
// engineering choice, replacing a plain tech-stack list.
import { useScrollReveal } from "../lib/useScrollReveal";

const DECISIONS = [
  {
    q: "Why Prompt Engineering?",
    a: "A single prompt can't replicate how a business analyst actually works. Splitting the process into an interview stage and a generation stage produces sharper, more complete requirements than asking for everything at once.",
  },
  {
    q: "Why Docker?",
    a: "Packaging the frontend and backend into one image means what runs on a laptop is exactly what runs in production - no “works on my machine” gap.",
  },
  {
    q: "Why GitHub Actions?",
    a: "Deployment shouldn't depend on someone remembering the right commands. Every push to main builds and ships itself, authenticated with OIDC so no AWS credentials are ever stored in the repo.",
  },
  {
    q: "Why ECS?",
    a: "A managed container service means scaling and recovery are handled by AWS, not by hand-rolled infrastructure scripts.",
  },
];

export default function EngineeringDecisionsSection() {
  const { ref, visible } = useScrollReveal();

  return (
    <section ref={ref} className="max-w-3xl mx-auto px-6 py-24 md:py-28">
      <div className="text-center mb-16">
        <div className="text-[11px] font-bold tracking-[0.09em] uppercase text-accent mb-3">
          Engineering Decisions
        </div>
        <h2 className="font-display font-extrabold text-3xl md:text-4xl tracking-tight text-ink">
          The reasoning, not just the stack
        </h2>
      </div>

      <div className="flex flex-col gap-4">
        {DECISIONS.map(({ q, a }, i) => (
          <div
            key={q}
            className="border border-border rounded-2xl px-6 py-5 transition-all duration-700 ease-out"
            style={{
              opacity: visible ? 1 : 0,
              transform: visible ? "translateY(0)" : "translateY(14px)",
              transitionDelay: `${i * 90}ms`,
            }}
          >
            <div className="font-display font-bold text-[15px] text-ink mb-1.5">{q}</div>
            <p className="text-[13.5px] leading-relaxed text-muted m-0">{a}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
