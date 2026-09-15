// Panel 2 of the homepage: the 4-step working flow, plus a 5th step that
// isn't built yet - visually separated and dimmed so it never reads as part
// of the working product.
const STEPS = [
  { n: "01", title: "Start with an idea. Or a mess of notes. Either works" },
  {
    n: "02",
    title: "Answer what it needs to know",
    desc: "Shaped by your category. Take a suggestion, or write your own.",
  },
  {
    n: "03",
    title: "Watch the document build as you go",
    desc: "Five sections take shape beside the conversation, not after it.",
  },
  {
    n: "04",
    title: "Review, refine, export",
    desc: "Three AI perspectives catch what's missing before you download.",
  },
];

// A hairline with a label sitting on top of it, matching-background masking
// the line where the label sits.
function HairlineLabel({ children, bgClass }) {
  return (
    <div className={`relative mb-10 h-px bg-border`}>
      <span
        className={`absolute left-0 top-1/2 -translate-y-1/2 ${bgClass} pr-3 text-[12.5px] font-semibold text-accent leading-none`}
      >
        {children}
      </span>
    </div>
  );
}

export default function HowItWorksSection() {
  return (
    <section className="bg-panel-2 rounded-[22px] min-[561px]:rounded-[30px] p-[46px_24px] min-[561px]:p-[74px_60px]">
      <h2
        className="font-display font-bold text-ink mb-10"
        style={{ fontSize: "clamp(25px, 3vw, 33px)", lineHeight: 1.2 }}
      >
        How it works
      </h2>

      <HairlineLabel bgClass="bg-panel-2">Process</HairlineLabel>

      <div className="grid grid-cols-1 min-[561px]:grid-cols-2 min-[901px]:grid-cols-4 gap-9">
        {STEPS.map((step) => (
          <div key={step.n} className="text-left">
            <div className="font-mono text-[13px] text-accent tabular-nums mb-2">{step.n}</div>
            <div className="font-display font-semibold text-base text-ink mb-1">{step.title}</div>
            {step.desc && (
              <p className="text-[14.5px] leading-[1.55] text-muted m-0">{step.desc}</p>
            )}
          </div>
        ))}
      </div>

      <div className="mt-10 pt-[26px] border-t border-border opacity-[.72]">
        <div className="font-mono text-[13px] text-accent tabular-nums mb-2">05</div>
        <div className="flex items-center flex-wrap gap-2.5 mb-1">
          <span className="font-display font-semibold text-base text-ink">
            Check against real standards
          </span>
          <span className="text-[11.5px] font-semibold text-muted border border-border rounded-full px-2.5 py-[3px] leading-none">
            IN DEVELOPMENT
          </span>
        </div>
        <p className="text-[14.5px] leading-[1.55] text-muted m-0">
          PDPL, ZATCA, INVEST, and EARS matched against your requirements automatically. Not
          built yet.
        </p>
      </div>
    </section>
  );
}
