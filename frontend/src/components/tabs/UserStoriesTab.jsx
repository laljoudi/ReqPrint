export default function UserStoriesTab({ userStories }) {
  return (
    <div className="space-y-3">
      {userStories.map((s, i) => (
        <div
          key={i}
          className="rounded-xl bg-story-bg border border-story-border px-4.5 py-3.5"
        >
          <span className="text-story-id font-semibold text-sm">
            {s.id} - {s.role}
          </span>
          <p className="text-sm text-ink mt-1">{s.story}</p>
        </div>
      ))}
    </div>
  );
}
