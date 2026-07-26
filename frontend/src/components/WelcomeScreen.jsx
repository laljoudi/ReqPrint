// Stage 1 (of welcome -> chat -> document): the landing page. No data, just a
// CTA at the bottom that moves App.jsx into the chat stage via the onStart prop.
//
// Structure: a product-focused hero, then the product story (workflow,
// benefits, the build timeline, engineering reasoning), then the closing CTA.
import HowItWorksSection from "./HowItWorksSection";
import WhyReqPrintSection from "./WhyReqPrintSection";
import HowItWasBuiltSection from "./HowItWasBuiltSection";
import EngineeringDecisionsSection from "./EngineeringDecisionsSection";

export default function WelcomeScreen({ onStart }) {
  return (
    <div className="min-h-screen">
      {/* Hero - project name, tagline, description, and a quiet scroll cue */}
      <section className="max-w-2xl mx-auto px-6 pt-32 pb-24 md:pt-40 md:pb-28 text-center">
        <h1 className="font-display font-extrabold text-5xl md:text-6xl tracking-tight text-ink mb-4">
          ReqPrint
        </h1>
        <p className="font-display font-bold text-lg md:text-xl text-accent tracking-tight mb-5">
          AI-Powered Requirements Engineering
        </p>
        <p className="text-[16px] md:text-lg text-muted leading-relaxed max-w-xl mx-auto">
          Transform a simple project idea into a structured Software Requirements
          Specification through a short series of AI-guided clarifying questions.
        </p>

        <div className="mt-16 flex justify-center text-hint" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </section>

      <HowItWorksSection />
      <WhyReqPrintSection />
      <HowItWasBuiltSection />
      <EngineeringDecisionsSection />

      {/* Closing CTA - the single entry point into the app */}
      <section className="border-t border-border">
        <div className="max-w-xl mx-auto px-6 py-24 text-center">
          <h2 className="font-display font-extrabold text-2xl md:text-3xl tracking-tight text-ink mb-8">
            Ready to write your first spec?
          </h2>
          <button
            onClick={onStart}
            className="inline-flex items-center gap-2.5 h-[50px] px-6 rounded-xl bg-accent hover:brightness-105 active:scale-[0.98] text-white font-display font-bold text-[15px] shadow-[0_10px_24px_rgba(186,85,211,0.28)] transition"
          >
            Describe your project
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14"></path>
              <path d="m12 5 7 7-7 7"></path>
            </svg>
          </button>
        </div>
      </section>
    </div>
  );
}
