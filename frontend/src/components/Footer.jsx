// Minimal site footer. Sits on the page background, no panel. Reuses the
// same placeholder constants WelcomeScreen.jsx defines, so editing those
// three lines updates this too.
import { YOUR_NAME, GITHUB_URL, LINKEDIN_URL } from "./WelcomeScreen";

export default function Footer() {
  return (
    <footer className="p-[26px_60px_46px] flex flex-wrap items-center justify-between gap-3 text-[13.5px] text-muted">
      <p className="m-0">ReqPrint — a personal project by {YOUR_NAME}</p>
      <div className="flex items-center gap-4">
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">
          GitHub
        </a>
        <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">
          LinkedIn
        </a>
      </div>
    </footer>
  );
}
