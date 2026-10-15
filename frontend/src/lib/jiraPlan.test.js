// Tests for the pure Jira-dialog helpers. Uses Node's built-in test runner (no
// dependency): from frontend/, run `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  hashDocument,
  parseCapacity,
  parseISODate,
  previewParts,
  previewPlan,
  previewText,
  safeHttpUrl,
  suggestProjectName,
  todayLocalISO,
  validateForm,
} from "./jiraPlan.js";

const plan = (over = {}) => previewPlan({ totalStories: 7, capacity: 3, weeks: 2, startISO: "2026-11-07", ...over });

test("preview: stories_per_sprint = capacity x sprint length, sprints = ceil(stories / that)", () => {
  assert.equal(plan({ capacity: 3, weeks: 2 }).perSprint, 6);
  assert.equal(plan({ capacity: 3, weeks: 2 }).sprints, 2); // 7 / 6
  assert.equal(plan({ capacity: 1, weeks: 3 }).sprints, 3); // 7 / 3
  assert.equal(plan({ capacity: 2, weeks: 4 }).sprints, 1); // 7 / 8
  assert.equal(plan({ totalStories: 12, capacity: 2, weeks: 3 }).sprints, 2); // exact multiple
  assert.equal(plan({ totalStories: 13, capacity: 2, weeks: 3 }).sprints, 3);
  assert.equal(plan({ totalStories: 0 }).sprints, 0);
  assert.equal(plan({ totalStories: 1, capacity: 50, weeks: 4 }).sprints, 1);
});

test("preview: sprints run back to back, so the end is start + sprints x length", () => {
  const p = plan({ capacity: 1, weeks: 3 }); // 3 sprints x 3 weeks from 7 Nov 2026
  assert.equal(p.start.toISOString(), "2026-11-07T00:00:00.000Z");
  assert.equal(p.end.toISOString(), "2027-01-09T00:00:00.000Z"); // 63 days later
  assert.equal(plan({ capacity: 2, weeks: 2 }).end.toISOString(), "2026-12-05T00:00:00.000Z"); // 2 x 2 weeks
});

test("preview text matches the requested format, with the per-sprint figure", () => {
  // the example from the brief: capacity 2 x 2-week sprints = 4 per sprint
  assert.equal(previewText(plan({ totalStories: 8, capacity: 2, weeks: 2, startISO: "2026-11-07" })), "8 stories · 4 per sprint · 2 sprints · 7 Nov → 5 Dec");
  assert.equal(previewText(plan({ capacity: 1, weeks: 3 })), "7 stories · 3 per sprint · 3 sprints · 7 Nov → 9 Jan");
  assert.equal(previewText(plan({ totalStories: 1 })), "1 story · 6 per sprint · 1 sprint · 7 Nov → 21 Nov"); // 3/week x 2 weeks
  assert.equal(previewText(plan({ totalStories: 0 })), "0 stories");
  assert.equal(previewText(plan({ startISO: "2026-09-01", totalStories: 1, capacity: 1, weeks: 1 })), "1 story · 1 per sprint · 1 sprint · 1 Sep → 8 Sep");
});

test("preview text: the per-sprint figure is always capacity x sprint length", () => {
  for (const capacity of [1, 2, 3, 7, 25, 50]) {
    for (const weeks of [1, 2, 3, 4]) {
      const text = previewText(plan({ totalStories: 9, capacity, weeks }));
      assert.ok(text.includes(` · ${capacity * weeks} per sprint · `), `${capacity} x ${weeks}: ${text}`);
    }
  }
});

test("preview text: parts appear in order and the sprint count still follows the per-sprint figure", () => {
  for (const [stories, capacity, weeks] of [[8, 2, 2], [7, 3, 2], [7, 1, 3], [100, 1, 1], [13, 2, 3], [3, 50, 4]]) {
    const p = plan({ totalStories: stories, capacity, weeks });
    const m = /^(\d+) stories? · (\d+) per sprint · (\d+) sprints? · \d+ [A-Z][a-z]{2} → \d+ [A-Z][a-z]{2}$/.exec(previewText(p));
    assert.ok(m, previewText(p));
    assert.deepEqual([Number(m[1]), Number(m[2]), Number(m[3])], [stories, capacity * weeks, Math.ceil(stories / (capacity * weeks))]);
  }
});

test("preview parts: the pieces the dialog keeps on one line each, joined = the preview text", () => {
  assert.deepEqual(previewParts(plan({ totalStories: 8, capacity: 2, weeks: 2 })), ["8 stories", "4 per sprint", "2 sprints", "7 Nov → 5 Dec"]);
  assert.deepEqual(previewParts(plan({ totalStories: 1 })), ["1 story", "6 per sprint", "1 sprint", "7 Nov → 21 Nov"]);
  assert.deepEqual(previewParts(plan({ totalStories: 0 })), ["0 stories"]);
  for (const over of [{}, { capacity: 1, weeks: 3 }, { totalStories: 100, capacity: 1, weeks: 1 }, { totalStories: 0 }]) {
    assert.equal(previewParts(plan(over)).join(" · "), previewText(plan(over)));
  }
});

test("preview handles past dates, leap days and month/year boundaries", () => {
  assert.equal(plan({ startISO: "2020-01-15" }).start.getUTCFullYear(), 2020);
  assert.equal(plan({ startISO: "2028-02-20", totalStories: 1, capacity: 1, weeks: 2 }).end.toISOString(), "2028-03-05T00:00:00.000Z");
  assert.equal(plan({ startISO: "2026-12-20", totalStories: 1, capacity: 1, weeks: 4 }).end.toISOString(), "2027-01-17T00:00:00.000Z");
});

test("preview refuses invalid input instead of guessing", () => {
  for (const over of [{ startISO: "" }, { startISO: "2026-02-30" }, { startISO: "tomorrow" }, { capacity: 0 }, { capacity: 51 }, { capacity: 2.5 },
    { capacity: NaN }, { weeks: 0 }, { weeks: 5 }, { weeks: "2" }, { totalStories: -1 }, { totalStories: 1.5 }]) {
    assert.equal(plan(over), null, JSON.stringify(over));
  }
});

test("dates: only real YYYY-MM-DD calendar dates parse", () => {
  assert.deepEqual(parseISODate("2028-02-29"), { y: 2028, m: 2, d: 29 });
  for (const bad of ["2027-02-29", "2026-13-01", "2026-00-10", "2026-04-31", "2026-10-8", "10/08/2026", "2026-10-08T00:00", "", null, undefined, 20261008]) {
    assert.equal(parseISODate(bad), null, String(bad));
  }
});

test("todayLocalISO is the local calendar date, zero-padded", () => {
  assert.equal(todayLocalISO(new Date(2026, 0, 5, 23, 59)), "2026-01-05");
  assert.equal(todayLocalISO(new Date(2026, 11, 31, 0, 0)), "2026-12-31");
});

test("capacity: a whole number from 1 to 50, else null", () => {
  for (const [text, expected] of [["1", 1], ["3", 3], ["50", 50], [" 7 ", 7], ["0", null], ["51", null], ["", null], ["2.5", null], ["-1", null], ["abc", null], ["1e1", null], ["٣", null]]) {
    assert.equal(parseCapacity(text), expected, JSON.stringify(text));
  }
});

test("form validation reports each problem and passes a good form", () => {
  const good = { name: "Library Booking System", startISO: "2026-11-07", capacityText: "3", totalStories: 7 };
  assert.deepEqual(validateForm(good), {});
  assert.ok(validateForm({ ...good, name: "   " }).name);
  assert.ok(validateForm({ ...good, name: "x".repeat(81) }).name);
  assert.deepEqual(validateForm({ ...good, name: "x".repeat(80) }), {});
  assert.ok(validateForm({ ...good, startISO: "" }).startDate);
  assert.ok(validateForm({ ...good, startISO: "1999-12-31" }).startDate);
  assert.ok(validateForm({ ...good, startISO: "2100-01-01" }).startDate);
  assert.deepEqual(validateForm({ ...good, startISO: "2020-01-15" }), {}); // the past is allowed
  assert.ok(validateForm({ ...good, capacityText: "0" }).capacity);
  assert.ok(validateForm({ ...good, capacityText: "" }).capacity);
  assert.ok(validateForm({ ...good, totalStories: 0 }).stories);
  assert.ok(validateForm({ ...good, totalStories: 101 }).stories);
  assert.deepEqual(validateForm({ ...good, totalStories: 100 }), {});
});

test("project name suggestion", () => {
  const cases = [
    ["I want to build a library booking system for university students", "Library Booking System"],
    ["A library booking system for university students", "Library Booking System"],
    ["We need to create an HR onboarding portal that tracks new hires", "HR Onboarding Portal"],
    ["Build me an expense tracker app, with receipts and reports", "Expense Tracker App"],
    ["Project category: FinTech\n\nI want to build a mobile app that lets freelancers track invoices", "Mobile App"],
    ["Project category: HR Tech\n\nLeave management system.\n\nOpen questions identified from this input - please prioritize asking about these:\n- who approves?", "Leave Management System"],
    ["online grocery delivery platform", "Online Grocery Delivery Platform"],
    ["nutrition coaching app with meal plans and a weekly check-in report for clients", "Nutrition Coaching App"],
    ["", "My Project"],
    ["   ", "My Project"],
    ["!!!", "My Project"],
    ["Project category: Other\n\n", "My Project"],
  ];
  for (const [input, expected] of cases) assert.equal(suggestProjectName(input), expected, JSON.stringify(input));
  assert.equal(suggestProjectName("نظام حجز المكتبات الجامعية"), "نظام حجز المكتبات الجامعية");
  assert.ok(suggestProjectName("word ".repeat(100)).length <= 80);
  assert.ok(suggestProjectName("a ".repeat(100)).split(" ").length <= 6);
  assert.ok(suggestProjectName("x".repeat(300)).length <= 80);
});

test("document hash: stable for the same document, different when anything changes", () => {
  const doc = { requirements: { functional: ["a"] }, user_stories: [{ id: "US-01", story: "x" }] };
  assert.equal(hashDocument(doc), hashDocument(structuredClone(doc)));
  assert.notEqual(hashDocument(doc), hashDocument({ ...doc, user_stories: [{ id: "US-01", story: "y" }] }));
  assert.notEqual(hashDocument(doc), hashDocument({ ...doc, assumptions: [] }));
  assert.match(hashDocument(doc), /^[0-9a-z]{6,12}$/);
});

test("document hash rarely collides", () => {
  const seen = new Set();
  for (let i = 0; i < 20000; i += 1) seen.add(hashDocument({ user_stories: [{ id: `US-${i}`, story: `story ${i}` }] }));
  assert.equal(seen.size, 20000);
});

test("safeHttpUrl lets http(s) through and nothing else", () => {
  assert.equal(safeHttpUrl("https://acme.atlassian.net/browse/LBS"), "https://acme.atlassian.net/browse/LBS");
  assert.equal(safeHttpUrl("http://localhost:8000/x"), "http://localhost:8000/x");
  for (const bad of ["javascript:alert(1)", "data:text/html,hi", "ftp://x/y", "//evil.com", "not a url", "", null, undefined, "JaVaScRiPt:alert(1)"]) {
    assert.equal(safeHttpUrl(bad), null, String(bad));
  }
});
