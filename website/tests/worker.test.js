import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { afterEach, test } from "node:test";
import worker from "../src/worker.js";

const catalog = JSON.parse(readFileSync(new URL("../public/brokers.json", import.meta.url)));
const migration = readFileSync(new URL("../migrations/0001_waitlist.sql", import.meta.url), "utf8");
const landingPage = readFileSync(new URL("../public/index.html", import.meta.url), "utf8");
const databases = [];
afterEach(() => { for (const db of databases.splice(0)) db.close(); });

function fixture() {
  const db = new DatabaseSync(":memory:");
  databases.push(db);
  db.exec(migration);
  const env = {
    ASSETS: { fetch: async () => Response.json(catalog) },
    WAITLIST_RATE_LIMITER: { limit: async () => ({ success: true }) },
    WAITLIST_DB: {
      prepare: (sql) => ({ bind: (...values) => ({ run: async () => db.prepare(sql).run(...values) }) }),
    },
  };
  const rows = () => db.prepare("SELECT * FROM waitlist ORDER BY id").all();
  return { env, rows };
}

const signup = (overrides = {}) => ({
  email: "person@example.invalid", brokers: ["zerodha", "easyequities", "degiro"],
  consent: true, website: "", ...overrides,
});

function request(data = signup(), options = {}) {
  return new Request("https://flyrel.example/api/waitlist", {
    method: "POST",
    headers: { Origin: "https://flyrel.example", "Content-Type": "application/json" },
    body: JSON.stringify(data), ...options,
  });
}

test("persists email, stable broker IDs and consent with a creation timestamp", async () => {
  const { env, rows } = fixture();
  const response = await worker.fetch(request(signup({ email: " Person@Example.invalid " })), env);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(response.headers.get("X-Content-Type-Options"), "nosniff");
  assert.equal(rows().length, 1);
  assert.equal(rows()[0].email, "person@example.invalid");
  assert.deepEqual(JSON.parse(rows()[0].broker_ids), ["degiro", "easyequities", "zerodha"]);
  assert.equal(rows()[0].consent_version, "early-access-v1");
  assert.ok(!Number.isNaN(Date.parse(rows()[0].created_at)));
});

test("retries and case variants keep one original entry and return indistinguishable responses", async () => {
  const { env, rows } = fixture();
  const first = await worker.fetch(request(), env);
  const retry = await worker.fetch(request(signup({ email: "PERSON@example.invalid", brokers: ["alpaca"] })), env);
  assert.equal(retry.status, first.status);
  assert.deepEqual(await retry.json(), await first.json());
  assert.equal(rows().length, 1);
  assert.ok(JSON.parse(rows()[0].broker_ids).includes("zerodha"));
});

test("Other is stored separately and duplicate broker IDs are normalized", async () => {
  const { env, rows } = fixture();
  const response = await worker.fetch(request(signup({ brokers: ["other", "other"], otherBroker: " Local broker " })), env);
  assert.equal(response.status, 200);
  assert.deepEqual(JSON.parse(rows()[0].broker_ids), ["other"]);
  assert.equal(rows()[0].other_broker, "Local broker");
});

test("discards custom broker input when Other is not selected", async () => {
  const { env, rows } = fixture();
  await worker.fetch(request(signup({ otherBroker: "unselected" })), env);
  assert.equal(rows()[0].other_broker, "");
});

test("rejects invalid emails, missing consent and invalid broker selections without writes", async () => {
  const invalid = [
    { email: "bad" }, { email: "a\n@example.com" }, { email: "x".repeat(255) + "@example.com" },
    { consent: false }, { consent: "true" }, { brokers: [] }, { brokers: ["unrecognized"] },
    { brokers: [null] }, { brokers: "zerodha" }, { brokers: Array(21).fill("zerodha") },
    { brokers: ["other"] }, { brokers: ["other"], otherBroker: "x".repeat(101) },
    { brokers: ["other"], otherBroker: "broker\nname" },
  ];
  for (const data of invalid) {
    const { env, rows } = fixture();
    assert.equal((await worker.fetch(request(signup(data)), env)).status, 400, JSON.stringify(data));
    assert.equal(rows().length, 0);
  }
});

test("parameterized custom names cannot modify schema", async () => {
  const { env, rows } = fixture();
  const name = "'); DROP TABLE waitlist; --";
  assert.equal((await worker.fetch(request(signup({ brokers: ["other"], otherBroker: name })), env)).status, 200);
  assert.equal(rows()[0].other_broker, name);
});

test("requires same-origin JSON POST and exposes no public lookup or export", async () => {
  const { env, rows } = fixture();
  for (const origin of ["https://elsewhere.example", "null", ""]) {
    const response = await worker.fetch(request(signup(), {
      headers: { Origin: origin, "Content-Type": "application/json" },
    }), env);
    assert.equal(response.status, 403);
  }
  assert.equal((await worker.fetch(request(signup(), { headers: { Origin: "https://flyrel.example" } }), env)).status, 415);
  for (const method of ["GET", "PUT", "DELETE", "OPTIONS"]) {
    const response = await worker.fetch(new Request("https://flyrel.example/api/waitlist", { method }), env);
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("Allow"), "POST");
  }
  assert.equal((await worker.fetch(new Request("https://flyrel.example/api/export"), env)).status, 404);
  assert.equal(rows().length, 0);
});

test("rejects malformed, non-object and oversized JSON, including streamed bodies", async () => {
  const { env, rows } = fixture();
  for (const data of [null, [], "text", 12]) {
    assert.equal((await worker.fetch(request(data), env)).status, 400);
  }
  assert.equal((await worker.fetch(request(signup(), { body: "{" }), env)).status, 400);
  assert.equal((await worker.fetch(request(signup({ otherBroker: "x".repeat(9000) })), env)).status, 413);
  const stream = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode("x".repeat(9000)));
    controller.close();
  } });
  assert.equal((await worker.fetch(request(signup(), { body: stream, duplex: "half" }), env)).status, 413);
  assert.equal(rows().length, 0);
});

test("honeypot submissions receive a generic response and are not stored", async () => {
  const { env, rows } = fixture();
  assert.equal((await worker.fetch(request(signup({ website: "bot.example" })), env)).status, 200);
  assert.equal(rows().length, 0);
});

test("rate limits before persistence and returns retry guidance", async () => {
  const { env, rows } = fixture();
  let key;
  env.WAITLIST_RATE_LIMITER.limit = async (input) => { key = input.key; return { success: false }; };
  const req = request();
  req.headers.set("CF-Connecting-IP", "192.0.2.1");
  const response = await worker.fetch(req, env);
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("Retry-After"), "60");
  assert.equal(key, "192.0.2.1");
  assert.equal(rows().length, 0);
});

test("missing bindings and storage failures never report a saved signup or leak details", async () => {
  const { env } = fixture();
  for (const binding of ["WAITLIST_DB", "WAITLIST_RATE_LIMITER"]) {
    assert.equal((await worker.fetch(request(), { ...env, [binding]: undefined })).status, 503);
  }
  env.WAITLIST_DB.prepare = () => { throw new Error("private database details"); };
  const response = await worker.fetch(request(), env);
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes("private database details"));
  env.ASSETS.fetch = async () => new Response("Not found", { status: 404 });
  assert.equal((await worker.fetch(request(), env)).status, 503);
});

test("the landing page's pre-rendered broker count matches the catalog", () => {
  assert.ok(landingPage.includes(`<span id="broker-count">${catalog.length}</span>`));
});

test("catalog IDs are unique and cover each requested world region without integration claims", () => {
  assert.equal(new Set(catalog.map((broker) => broker.id)).size, catalog.length);
  for (const region of ["Global", "North America", "Europe", "Asia", "Africa", "South America", "Oceania", "Middle East"]) {
    assert.ok(catalog.some((broker) => broker.region === region), region);
  }
  for (const broker of catalog) {
    assert.match(broker.id, /^[a-z0-9-]+$/);
    assert.equal(new URL(broker.url).protocol, "https:");
    assert.ok(broker.name && broker.markets);
    assert.equal(broker.supported, undefined);
  }
});
