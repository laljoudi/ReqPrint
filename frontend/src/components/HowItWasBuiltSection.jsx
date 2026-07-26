// Landing page section: a single quiet vertical timeline consolidating the
// engineering story. Each technology is mentioned once, with its logo inline
// beside the name. Logos are small and monochrome (currentColor -> text-muted)
// rather than the brands' original colors, to stay consistent with the quiet
// palette. No gradients, no large icons, no animation.
const logoBase = { width: 16, height: 16, viewBox: "0 0 24 24", "aria-hidden": true };

function ReactLogo(props) {
  return (
    <svg {...logoBase} fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <circle cx="12" cy="12" r="1.9" fill="currentColor" stroke="none" />
      <ellipse cx="12" cy="12" rx="10" ry="4" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" />
    </svg>
  );
}

function FastAPILogo(props) {
  return (
    <svg {...logoBase} fill="currentColor" {...props}>
      <path d="M12 1.5 3.5 12h5.7l-2.1 10.5L20.5 11h-6.2L12 1.5Z" />
    </svg>
  );
}

function GeminiLogo(props) {
  return (
    <svg {...logoBase} fill="currentColor" {...props}>
      <path d="M12 2c.6 4.4 1.6 6.9 3.4 8.6 1.8 1.8 4.3 2.8 8.6 3.4-4.4.6-6.9 1.6-8.6 3.4-1.8 1.8-2.8 4.3-3.4 8.6-.6-4.4-1.6-6.9-3.4-8.6C6.8 15.6 4.3 14.6 0 14c4.4-.6 6.9-1.6 8.6-3.4C10.4 8.9 11.4 6.4 12 2Z" />
    </svg>
  );
}

function DockerLogo(props) {
  return (
    <svg {...logoBase} fill="currentColor" {...props}>
      <path d="M22.5 10.2c-.5-.4-1.6-.5-2.4-.4-.1-.8-.6-1.5-1.3-2.1l-.4-.3-.3.4c-.5.6-.7 1.6-.6 2.3-.4.2-1 .5-1.9.5H2.2c-.2.9-.2 3.6 1.5 5.8 1.3 1.6 3.2 2.4 5.8 2.4 5.5 0 9.6-2.5 11.5-7.1 1 0 2-.1 2.6-.9.3-.4.5-.9.6-1.4l.1-.5-.7-.7Z" />
      <rect x="4" y="6.3" width="2.6" height="2.4" />
      <rect x="7.1" y="6.3" width="2.6" height="2.4" />
      <rect x="10.2" y="6.3" width="2.6" height="2.4" />
      <rect x="7.1" y="3.4" width="2.6" height="2.4" />
      <rect x="10.2" y="3.4" width="2.6" height="2.4" />
    </svg>
  );
}

function AWSLogo(props) {
  return (
    <svg {...logoBase} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 15.5c4.5 3 13.5 3 18 0" />
      <path d="M17 14.2c1.7.4 3 1 4 1.8" />
      <path d="M18.7 13.6 21 16l-2.6.6" />
    </svg>
  );
}

function GitHubLogo(props) {
  return (
    <svg {...logoBase} fill="currentColor" {...props}>
      <path d="M12 .5C5.73.5.5 5.74.5 12.02c0 5.08 3.29 9.38 7.86 10.9.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.78 2.71 1.26 3.37.97.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.68 0-1.25.45-2.28 1.19-3.09-.12-.3-.52-1.48.11-3.07 0 0 .97-.31 3.18 1.18a11 11 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.24 2.77.12 3.06.74.81 1.19 1.84 1.19 3.1 0 4.41-2.69 5.38-5.25 5.67.42.36.78 1.06.78 2.14v3.18c0 .31.21.67.8.56A10.53 10.53 0 0 0 23.5 12C23.5 5.74 18.27.5 12 .5Z" />
    </svg>
  );
}

const TIMELINE = [
  {
    title: "React + FastAPI",
    logos: [ReactLogo, FastAPILogo],
    body: "A single-page interface backed by a REST API, served as one application.",
  },
  {
    title: "Prompt Engineering",
    logos: [],
    body: "A multi-stage strategy that runs a requirements interview before generating the document.",
  },
  {
    title: "Google Gemini",
    logos: [GeminiLogo],
    body: "Powers the analyst questions and the structured requirements output.",
  },
  {
    title: "Docker",
    logos: [DockerLogo],
    body: "A multi-stage build: Node compiles the frontend, Python runs the API, shipped as one image.",
  },
  {
    title: "Amazon ECR + ECS",
    logos: [AWSLogo],
    body: "The image is stored in ECR and deployed as a managed container on AWS.",
  },
  {
    title: "GitHub Actions",
    logos: [GitHubLogo],
    body: "Every push to main builds, pushes, and redeploys automatically, authenticated with OIDC, no stored credentials.",
  },
];

export default function HowItWasBuiltSection() {
  return (
    <section className="max-w-2xl mx-auto px-6 py-24 md:py-28">
      <div className="text-center mb-16">
        <div className="text-[11px] font-bold tracking-[0.09em] uppercase text-accent mb-3">
          Under the Hood
        </div>
        <h2 className="font-display font-extrabold text-3xl md:text-4xl tracking-tight text-ink">
          How ReqPrint Was Built
        </h2>
      </div>

      <div className="relative pl-7">
        <div className="absolute left-[3px] top-1.5 bottom-1.5 w-px bg-border" />
        {TIMELINE.map((item, i) => (
          <div key={item.title} className={`relative ${i > 0 ? "mt-9" : ""}`}>
            <span className="absolute -left-7 top-1.5 w-[7px] h-[7px] rounded-full bg-accent" />
            <div className="flex items-center gap-2">
              {item.logos.map((Logo, j) => (
                <Logo key={j} className="text-muted shrink-0" />
              ))}
              <span className="font-display font-bold text-[15px] text-ink">{item.title}</span>
            </div>
            <div className="text-sm text-muted leading-relaxed mt-1">{item.body}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
