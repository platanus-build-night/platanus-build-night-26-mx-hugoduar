const API = process.env.NEXT_PUBLIC_NOCTUA_API ?? "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_NOCTUA_TOKEN ?? "";

const headers = () => ({ Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" });

export async function getQueue(kind?: string) {
  const url = new URL(`${API}/api/queue`);
  if (kind) url.searchParams.set("kind", kind);
  const r = await fetch(url, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function getArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function approveArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}/approve`, { method: "POST", headers: headers() });
  return r.json();
}

export async function rejectArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}/reject`, { method: "POST", headers: headers() });
  return r.json();
}

export async function getMission(id: number) {
  const r = await fetch(`${API}/api/missions/${id}`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function getProducers() {
  const r = await fetch(`${API}/api/producers`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function updateRubric(key: string, rubric_md: string) {
  const r = await fetch(`${API}/api/producers/${key}/rubric`, {
    method: "PUT", headers: headers(), body: JSON.stringify({ rubric_md }),
  });
  return r.json();
}
