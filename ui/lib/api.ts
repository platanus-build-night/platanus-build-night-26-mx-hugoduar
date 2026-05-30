const API = process.env.NEXT_PUBLIC_NOCTUA_API ?? "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_NOCTUA_TOKEN ?? "";

const headers = () => ({ Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" });

async function call(input: URL | string, init?: RequestInit) {
  const r = await fetch(input, { ...(init ?? {}), headers: headers(), cache: "no-store" });
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(
      `Noctua API ${r.status} ${r.statusText} for ${typeof input === "string" ? input : input.toString()}` +
        (body ? `\n${body.slice(0, 500)}` : ""),
    );
  }
  return r.json();
}

export async function getQueue(kind?: string) {
  const url = new URL(`${API}/api/queue`);
  if (kind) url.searchParams.set("kind", kind);
  return call(url);
}

export async function getArtifact(id: number) {
  return call(`${API}/api/artifacts/${id}`);
}

export async function approveArtifact(id: number) {
  return call(`${API}/api/artifacts/${id}/approve`, { method: "POST" });
}

export async function rejectArtifact(id: number) {
  return call(`${API}/api/artifacts/${id}/reject`, { method: "POST" });
}

export async function getMission(id: number) {
  return call(`${API}/api/missions/${id}`);
}

export async function listMissions(state?: string) {
  const url = new URL(`${API}/api/missions`);
  if (state) url.searchParams.set("state", state);
  return call(url);
}

export async function getMissionPlans(id: number) {
  return call(`${API}/api/missions/${id}/plans`);
}

export async function listSandboxes(state?: string) {
  const url = new URL(`${API}/api/sandboxes`);
  if (state) url.searchParams.set("state", state);
  return call(url);
}

export async function getMissionSandboxes(missionId: number) {
  return call(`${API}/api/missions/${missionId}/sandboxes`);
}

export async function getProducers() {
  return call(`${API}/api/producers`);
}

export async function updateRubric(key: string, rubric_md: string) {
  return call(`${API}/api/producers/${key}/rubric`, {
    method: "PUT",
    body: JSON.stringify({ rubric_md }),
  });
}
