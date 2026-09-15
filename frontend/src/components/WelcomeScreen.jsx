// Stage 1 (of welcome -> workspace): the landing page. No data, just a
// CTA at the bottom that moves App.jsx into the workspace stage via the
// onStart prop.
//
// Structure: hero panel, how-it-works panel, how-it's-built panel, closing
// panel, footer (no panel, sits on the page background).
import HowItWorksSection from "./HowItWorksSection";
import HowItWasBuiltSection from "./HowItWasBuiltSection";
import Footer from "./Footer";

// Three values below are literal placeholder tokens the site owner fills in
// by hand - not real names/URLs, and not guessed from anywhere in the repo.
// Defined once here and imported everywhere else they're used (Footer.jsx),
// so editing these three lines updates every occurrence.
export const YOUR_NAME = "Layan Aljoudi";
export const GITHUB_URL = "https://github.com/laljoudi/ReqPrint.git";
export const LINKEDIN_URL = "https://www.linkedin.com/in/layan-aljoudi/";

export default function WelcomeScreen({ onStart }) {
  return (
    <div className="min-h-screen">
      <div className="max-w-[1080px] mx-auto px-[14px] py-[14px] flex flex-col gap-3.5">
        {/* Panel 1: Hero - deliberately short, nothing but wordmark + h1 */}
        <section className="bg-panel rounded-[22px] min-[561px]:rounded-[30px] p-[38px_24px] min-[561px]:p-[52px_60px]">
          <div className="text-[25px] leading-none tracking-[-0.03em] font-display font-bold text-ink mb-[26px]">
            ReqPrint
          </div>
          <h1
            className="font-display font-bold text-ink max-w-[19ch]"
            style={{ fontSize: "clamp(32px, 4.2vw, 46px)", lineHeight: 1.16 }}
          >
            From a project description to a structured requirements document
          </h1>
        </section>

        {/* Panel 2 */}
        <HowItWorksSection />

        {/* Panel 3 */}
        <HowItWasBuiltSection />

        {/* Panel 4: Closing - the single entry point into the app */}
        <section className="bg-panel-2 rounded-[22px] min-[561px]:rounded-[30px] p-[46px_24px] min-[561px]:p-[74px_60px] text-center">
          <h2
            className="font-display font-bold text-ink mb-8"
            style={{ fontSize: "clamp(25px, 3vw, 33px)", lineHeight: 1.2 }}
          >
            Ready to write your first spec?
          </h2>
          <button
            onClick={onStart}
            className="inline-flex items-center px-8 py-[15px] rounded-full bg-accent hover:brightness-105 active:scale-[0.98] text-white font-display font-semibold text-base transition"
          >
            Describe your project
          </button>
        </section>
      </div>

      <Footer />
    </div>
  );
}
