// Tests for what pushToJira sends. fetch is stubbed; run with `npm test`.
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { pushToJira } from "./api.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

async function bodySentFor(params) {
  let sent;
  globalThis.fetch = async (url, options) => {
    sent = { url, body: JSON.parse(options.body) };
    return new Response(JSON.stringify({ project_key: "LBS" }), { status: 200 });
  };
  await pushToJira({ projectName: "P", capacityPerWeek: 2, sprintLengthWeeks: 2, startDate: "2026-11-07", requirements: { user_stories: [] }, ...params });
  return sent;
}

test("sub-tasks on: create_subtasks is true", async () => {
  const { url, body } = await bodySentFor({ subtasks: true });
  assert.equal(url, "/api/jira/push");
  assert.equal(body.create_subtasks, true);
});

test("sub-tasks off: create_subtasks is an explicit false", async () => {
  assert.equal((await bodySentFor({ subtasks: false })).body.create_subtasks, false);
});

test("anything that isn't exactly true is sent as false (the backend only accepts real booleans)", async () => {
  for (const value of [undefined, null, "true", 1, 0, "yes", []]) {
    assert.equal((await bodySentFor({ subtasks: value })).body.create_subtasks, false, String(value));
  }
});

test("the rest of the request is unchanged by the new flag", async () => {
  const { body } = await bodySentFor({ subtasks: true, category: "HR Tech" });
  const { requirements, ...rest } = body;
  assert.deepEqual(rest, {
    mode: "create",
    project_name: "P",
    capacity_per_week: 2,
    sprint_length_weeks: 2,
    start_date: "2026-11-07",
    create_subtasks: true,
    category: "HR Tech",
  });
  assert.deepEqual(requirements, { user_stories: [] });
});
