// Landing page section: 4 quiet feature cards. Each explains a benefit to
// the visitor, not how it's implemented.
import { useScrollReveal } from "../lib/useScrollReveal";

function ChatIcon(props) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 11.5a8.4 8.4 0 0 1-8.4 8.4 8.5 8.5 0 0 1-3.8-.9L3 20l1.1-5.6a8.4 8.4 0 1 1 16.9-2.9Z" />
    </svg>
  );
}
function LayersIcon(props) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </svg>
  );
}
function CloudIcon(props) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M7 18a4.5 4.5 0 0 1-.5-8.97A5.5 5.5 0 0 1 17.2 8.3 4 4 0 0 1 17 16.4" />
      <path d="M7 18h10" />
    </svg>
  );
}
function ExportIcon(props) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 3v11" />
      <path d="m7.5 10 4.5 4.5 4.5-4.5" />
      <path d="M5 19h14" />
    </svg>
  );
}

const FEATURES = [
  {
    icon: ChatIcon,
    title: "AI-Guided Requirement Elicitation",
    body: "ReqPrint asks the clarifying questions a business analyst would, drawing out details you didn't know to write down.",
  },
  {
    icon: LayersIcon,
    title: "Structured SRS Output",
    body: "Functional and non-functional requirements, user stories, acceptance criteria, and use cases, laid out in clear sections the way a real spec is.",
  },
  {
    icon: CloudIcon,
    title: "Refine As You Go",
    body: "Not quite right? Adjust any section through the refine panel until the requirements match what you actually meant.",
  },
  {
    icon: ExportIcon,
    title: "Export When Ready",
    body: "Once it looks right, one click downloads the whole spec as a polished .docx, ready to share.",
  },
];

export default function WhyReqPrintSection() {
  const { ref, visible } = useScrollReveal();

  return (
    <section ref={ref} className="max-w-5xl mx-auto px-6 py-24 md:py-28">
      <div className="text-center mb-16">
        <div className="text-[11px] font-bold tracking-[0.09em] uppercase text-accent mb-3">
          Why ReqPrint
        </div>
        <h2 className="font-display font-extrabold text-3xl md:text-4xl tracking-tight text-ink">
          Built for the way requirements actually get written
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {FEATURES.map(({ icon: Icon, title, body }, i) => (
          <div
            key={title}
            className="border border-border rounded-2xl p-7 transition-all duration-700 ease-out hover:border-accent/30"
            style={{
              opacity: visible ? 1 : 0,
              transform: visible ? "translateY(0)" : "translateY(16px)",
              transitionDelay: `${i * 90}ms`,
            }}
          >
            <div className="w-10 h-10 rounded-full bg-accent/10 text-accent flex items-center justify-center mb-5">
              <Icon />
            </div>
            <div className="font-display font-bold text-[15.5px] text-ink mb-2">{title}</div>
            <p className="text-[13.5px] leading-relaxed text-muted m-0">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
