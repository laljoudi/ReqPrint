import Logo from "./Logo";

export default function Header() {
  return (
    <div className="flex items-center gap-3 border-b border-border pb-3.5 mb-6">
      <Logo />
      <span className="font-semibold text-xl text-ink">ReqPrint</span>
      <span className="text-sm text-muted border-l border-border pl-3">
        AI business analysis assistant
      </span>
    </div>
  );
}
