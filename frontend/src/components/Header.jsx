// Top bar shown on every screen once the user is logged in.
export default function Header() {
  return (
    <div className="flex items-center gap-3 border-b border-border pb-3.5 mb-6">
      <div className="flex items-center justify-center w-[34px] h-[34px] rounded-lg bg-accent text-white font-bold text-lg shrink-0">
        R
      </div>
      <span className="font-semibold text-xl text-ink">ReqPrint</span>
      <span className="text-sm text-muted border-l border-border pl-3">
        AI business analysis assistant
      </span>
    </div>
  );
}
