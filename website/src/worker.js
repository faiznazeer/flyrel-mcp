const MAX_BODY_BYTES = 8192;
const SUCCESS = { message: "You’re on the list. We’ll be in touch about early access." };

function json(data, status = 200, extraHeaders = {}) {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...extraHeaders,
    },
  });
}

async function boundedBody(request) {
  if (Number(request.headers.get("Content-Length")) > MAX_BODY_BYTES) return null;
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}

export async function joinWaitlist(request, env) {
  if (request.method !== "POST") {
    return json({ error: "Use POST to join the waitlist." }, 405, { Allow: "POST" });
  }
  const url = new URL(request.url);
  if (request.headers.get("Origin") !== url.origin) {
    return json({ error: "Please submit the form from this website." }, 403);
  }
  if (request.headers.get("Content-Type")?.split(";")[0].trim() !== "application/json") {
    return json({ error: "Send JSON form data." }, 415);
  }
  if (!env.WAITLIST_DB || !env.WAITLIST_RATE_LIMITER) {
    return json({ error: "The waitlist is temporarily unavailable. Please try again later." }, 503);
  }

  try {
    const { success } = await env.WAITLIST_RATE_LIMITER.limit({
      key: request.headers.get("CF-Connecting-IP") || "local",
    });
    if (!success) {
      return json({ error: "Too many attempts. Please try again in a minute." }, 429, {
        "Retry-After": "60",
      });
    }
    const body = await boundedBody(request);
    if (body === null) return json({ error: "The form is too large." }, 413);
    let data;
    try {
      data = JSON.parse(body);
    } catch {
      return json({ error: "Please check the form and try again." }, 400);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return json({ error: "Please check the form and try again." }, 400);
    }
    // A filled, visually hidden website field is a bot signal. Store nothing.
    if (data.website) return json(SUCCESS);
    const email = typeof data.email === "string" ? data.email.trim().toLowerCase() : "";
    if (email.length > 254 || !/^[^\s@\x00-\x1f\x7f]+@[^\s@\x00-\x1f\x7f]+\.[^\s@\x00-\x1f\x7f]+$/.test(email)) {
      return json({ error: "Enter a valid email address." }, 400);
    }
    if (data.consent !== true) {
      return json({ error: "Please agree to receive early-access emails." }, 400);
    }
    if (!Array.isArray(data.brokers) || data.brokers.length < 1 || data.brokers.length > 20
      || !data.brokers.every((id) => typeof id === "string")) {
      return json({ error: "Select between 1 and 20 brokers." }, 400);
    }
    const catalogResponse = await env.ASSETS.fetch(new Request(new URL("/brokers.json", url)));
    if (!catalogResponse.ok) throw new Error("Catalog unavailable");
    const catalog = await catalogResponse.json();
    const allowed = new Set([...catalog.map((broker) => broker.id), "other"]);
    if (data.brokers.some((id) => !allowed.has(id))) {
      return json({ error: "Choose brokers from the list, or select Other." }, 400);
    }
    const brokers = [...new Set(data.brokers)].sort();
    const otherBroker = brokers.includes("other") && typeof data.otherBroker === "string"
      ? data.otherBroker.trim() : "";
    if (brokers.includes("other") && (!otherBroker || otherBroker.length > 100
      || /[\x00-\x1f\x7f]/.test(otherBroker))) {
      return json({ error: "Enter your other broker’s name (up to 100 characters)." }, 400);
    }
    // Retries and duplicates never overwrite the original signup or reveal membership.
    await env.WAITLIST_DB.prepare(
      `INSERT INTO waitlist (email, broker_ids, other_broker, consent_version)
       VALUES (?, ?, ?, ?) ON CONFLICT(email) DO NOTHING`,
    ).bind(email, JSON.stringify(brokers), otherBroker, "early-access-v1").run();
    return json(SUCCESS);
  } catch {
    // Never echo or log email addresses, request bodies, IPs, or database errors.
    return json({ error: "We couldn’t save your signup. Please try again shortly." }, 503);
  }
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/api/waitlist") return joinWaitlist(request, env);
    if (pathname.startsWith("/api/")) return json({ error: "Not found." }, 404);
    return env.ASSETS.fetch(request);
  },
};
