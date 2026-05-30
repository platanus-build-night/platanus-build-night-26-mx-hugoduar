"use client";
import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls, Grid, Edges, Bounds } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

export interface CadPreview {
  title?: string;
  snippet?: string;
  model_url?: string;
  model_format?: "stl" | "glb" | "gltf";
  dimensions?: { x?: number; y?: number; z?: number } | number[];
}

export interface CadValidation {
  fea_max_stress_mpa?: number;
  yield_strength_mpa?: number;
  safety_factor?: number;
}

interface Props {
  preview?: CadPreview;
  validation?: CadValidation;
  height?: number;
}

type PartKind = "gear" | "bracket" | "shaft" | "flange" | "housing" | "plate" | "block";

function classifyPart(title: string | undefined, snippet: string | undefined): PartKind {
  const text = `${title ?? ""} ${snippet ?? ""}`.toLowerCase();
  if (/\bgear|sprocket|pinion\b/.test(text)) return "gear";
  if (/\b(bolt|screw|fastener|stud|threaded[-\s]?rod|m\d+\b)/.test(text)) return "shaft";
  if (/\bshaft|axle|rod|spindle|pin\b/.test(text)) return "shaft";
  if (/\bflange|coupling|hub\b/.test(text)) return "flange";
  if (/\bbracket|mount|arm|clip|jig\b/.test(text)) return "bracket";
  if (/\bhousing|case|enclosure|chassis\b/.test(text)) return "housing";
  if (/\bplate|panel|sheet\b/.test(text)) return "plate";
  return "block";
}

function parseDims(preview?: CadPreview): [number, number, number] {
  const d = preview?.dimensions;
  if (Array.isArray(d) && d.length >= 3) {
    return [d[0], d[1], d[2]].map(toUnit) as [number, number, number];
  }
  if (d && typeof d === "object" && !Array.isArray(d)) {
    return [toUnit(d.x ?? 1), toUnit(d.y ?? 1), toUnit(d.z ?? 1)];
  }
  const txt = preview?.snippet ?? "";
  const nums = [...txt.matchAll(/(\d+(?:\.\d+)?)\s*mm/gi)].slice(0, 3).map(m => parseFloat(m[1]));
  if (nums.length === 3) return nums.map(toUnit) as [number, number, number];
  if (nums.length === 2) return [toUnit(nums[0]), toUnit(nums[1]), toUnit(Math.min(...nums) * 0.4)];
  return [1.2, 1.2, 0.8];
}

function toUnit(mm: number): number {
  return Math.max(0.1, Math.min(4, mm / 25));
}

function bboxLabel(dims: [number, number, number], preview?: CadPreview): string {
  const d = preview?.dimensions;
  const fromPreview =
    Array.isArray(d) && d.length >= 3
      ? `${d[0]}×${d[1]}×${d[2]} mm`
      : d && typeof d === "object" && !Array.isArray(d) && d.x && d.y && d.z
        ? `${d.x}×${d.y}×${d.z} mm`
        : null;
  if (fromPreview) return fromPreview;
  const back = dims.map(v => Math.round(v * 25)).join("×");
  return `~${back} mm`;
}

function safetyTone(sf?: number): { label: string; color: string } {
  if (sf === undefined) return { label: "—", color: "#a1a1aa" };
  if (sf >= 2) return { label: "robust", color: "#34d399" };
  if (sf >= 1.5) return { label: "ok", color: "#86efac" };
  if (sf >= 1) return { label: "marginal", color: "#fbbf24" };
  return { label: "fails", color: "#f87171" };
}

function stressUtil(stress?: number, yieldStrength?: number): number | null {
  if (!stress || !yieldStrength || yieldStrength <= 0) return null;
  return Math.min(1, stress / yieldStrength);
}

function material(stressRatio: number | null): THREE.MeshStandardMaterial {
  const tint = stressRatio == null
    ? new THREE.Color("#a1a1aa")
    : new THREE.Color().setHSL(0.33 - 0.33 * stressRatio, 0.55, 0.55);
  return new THREE.MeshStandardMaterial({
    color: tint,
    metalness: 0.55,
    roughness: 0.35,
  });
}

function Gear({ dims, mat }: { dims: [number, number, number]; mat: THREE.Material }) {
  const teeth = 18;
  const r = Math.max(dims[0], dims[1]) / 2;
  const h = dims[2];
  const toothW = (Math.PI * 2 * r) / teeth / 1.8;
  return (
    <group>
      <mesh castShadow receiveShadow material={mat}>
        <cylinderGeometry args={[r, r, h, 64]} />
      </mesh>
      {Array.from({ length: teeth }).map((_, i) => {
        const a = (i / teeth) * Math.PI * 2;
        return (
          <mesh
            key={i}
            position={[Math.cos(a) * (r + toothW * 0.5), 0, Math.sin(a) * (r + toothW * 0.5)]}
            rotation={[0, -a, 0]}
            material={mat}
            castShadow
          >
            <boxGeometry args={[toothW, h * 0.92, toothW]} />
          </mesh>
        );
      })}
      <mesh material={mat}>
        <cylinderGeometry args={[r * 0.18, r * 0.18, h * 1.05, 32]} />
      </mesh>
    </group>
  );
}

function Shaft({ dims, mat }: { dims: [number, number, number]; mat: THREE.Material }) {
  const r = Math.min(dims[0], dims[2]) / 2;
  const h = dims[1];
  return (
    <group>
      <mesh castShadow receiveShadow material={mat}>
        <cylinderGeometry args={[r, r, h, 48]} />
      </mesh>
      <mesh position={[0, h / 2 + r * 0.15, 0]} material={mat} castShadow>
        <cylinderGeometry args={[r * 1.4, r * 1.4, r * 0.3, 32]} />
      </mesh>
      <mesh position={[0, -h / 2 - r * 0.15, 0]} material={mat} castShadow>
        <cylinderGeometry args={[r * 1.4, r * 1.4, r * 0.3, 32]} />
      </mesh>
    </group>
  );
}

function Flange({ dims, mat }: { dims: [number, number, number]; mat: THREE.Material }) {
  const r = Math.max(dims[0], dims[2]) / 2;
  const h = dims[1] * 0.5;
  return (
    <group>
      <mesh castShadow receiveShadow material={mat}>
        <cylinderGeometry args={[r * 1.4, r * 1.4, h * 0.4, 48]} />
      </mesh>
      <mesh position={[0, h * 0.55, 0]} castShadow material={mat}>
        <cylinderGeometry args={[r * 0.6, r * 0.6, h, 32]} />
      </mesh>
      {Array.from({ length: 6 }).map((_, i) => {
        const a = (i / 6) * Math.PI * 2;
        return (
          <mesh key={i} position={[Math.cos(a) * r * 1.1, 0, Math.sin(a) * r * 1.1]} material={mat}>
            <cylinderGeometry args={[r * 0.12, r * 0.12, h * 0.6, 16]} />
          </mesh>
        );
      })}
    </group>
  );
}

function Bracket({ dims, mat }: { dims: [number, number, number]; mat: THREE.Material }) {
  const [w, h, d] = dims;
  return (
    <group>
      <mesh castShadow receiveShadow material={mat}>
        <boxGeometry args={[w, h * 0.18, d]} />
      </mesh>
      <mesh
        position={[0, h / 2, -d / 2 + h * 0.09]}
        castShadow
        material={mat}
      >
        <boxGeometry args={[w, h, h * 0.18]} />
      </mesh>
      {[-w / 3, w / 3].map((x, i) => (
        <mesh key={i} position={[x, -h * 0.05, 0]} material={mat}>
          <cylinderGeometry args={[h * 0.08, h * 0.08, h * 0.25, 16]} />
        </mesh>
      ))}
    </group>
  );
}

function Housing({ dims, mat }: { dims: [number, number, number]; mat: THREE.Material }) {
  return (
    <group>
      <mesh castShadow receiveShadow material={mat}>
        <boxGeometry args={dims} />
      </mesh>
      <mesh material={mat} position={[0, dims[1] / 2 + 0.02, 0]}>
        <boxGeometry args={[dims[0] * 0.96, 0.02, dims[2] * 0.96]} />
      </mesh>
    </group>
  );
}

function ParametricPart({
  kind,
  dims,
  stressRatio,
}: {
  kind: PartKind;
  dims: [number, number, number];
  stressRatio: number | null;
}) {
  const mat = useMemo(() => material(stressRatio), [stressRatio]);
  const group = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.15;
  });
  return (
    <group ref={group}>
      {kind === "gear" && <Gear dims={dims} mat={mat} />}
      {kind === "shaft" && <Shaft dims={dims} mat={mat} />}
      {kind === "flange" && <Flange dims={dims} mat={mat} />}
      {kind === "bracket" && <Bracket dims={dims} mat={mat} />}
      {kind === "housing" && <Housing dims={dims} mat={mat} />}
      {(kind === "plate" || kind === "block") && (
        <mesh castShadow receiveShadow material={mat}>
          <boxGeometry args={dims} />
          <Edges color="#0006" />
        </mesh>
      )}
    </group>
  );
}

function StlMesh({ url, stressRatio }: { url: string; stressRatio: number | null }) {
  const geometry = useLoader(STLLoader, url);
  const mat = useMemo(() => material(stressRatio), [stressRatio]);
  const group = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.15;
  });
  return (
    <group ref={group}>
      <mesh geometry={geometry} material={mat} castShadow receiveShadow />
    </group>
  );
}

function GlbMesh({ url }: { url: string }) {
  const gltf = useLoader(GLTFLoader, url);
  const group = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.15;
  });
  return (
    <group ref={group}>
      <primitive object={gltf.scene} />
    </group>
  );
}

function Scene({ preview, validation }: { preview?: CadPreview; validation?: CadValidation }) {
  const stressRatio = stressUtil(validation?.fea_max_stress_mpa, validation?.yield_strength_mpa);
  const dims = parseDims(preview);
  const kind = classifyPart(preview?.title, preview?.snippet);
  const fmt = preview?.model_format ??
    (preview?.model_url?.toLowerCase().endsWith(".stl")
      ? "stl"
      : preview?.model_url?.toLowerCase().match(/\.(glb|gltf)$/)
        ? "glb"
        : undefined);
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 8, 4]} intensity={1.4} castShadow />
      <directionalLight position={[-4, 3, -6]} intensity={0.7} color="#a5b4fc" />
      <hemisphereLight args={["#cbd5e1", "#0a0a0d", 0.4]} />
      <Bounds fit clip observe margin={1.4}>
        {preview?.model_url && fmt === "stl" && (
          <StlMesh url={preview.model_url} stressRatio={stressRatio} />
        )}
        {preview?.model_url && (fmt === "glb" || fmt === "gltf") && (
          <GlbMesh url={preview.model_url} />
        )}
        {!preview?.model_url && (
          <ParametricPart kind={kind} dims={dims} stressRatio={stressRatio} />
        )}
      </Bounds>
      <Grid
        position={[0, -1.4, 0]}
        args={[20, 20]}
        cellSize={0.3}
        cellThickness={0.6}
        cellColor="#3f3f46"
        sectionSize={1.5}
        sectionThickness={1}
        sectionColor="#52525b"
        fadeDistance={18}
        fadeStrength={1}
        infiniteGrid
      />
      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        minDistance={2}
        maxDistance={20}
      />
    </>
  );
}

function Pill({
  label,
  value,
  hint,
  color,
}: {
  label: string;
  value: string;
  hint?: string;
  color?: string;
}) {
  return (
    <div className="rounded-md bg-background/60 backdrop-blur px-3 py-2 ring-1 ring-border min-w-[110px]">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className="text-sm font-semibold tabular-nums leading-tight"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
      {hint && <div className="text-[10px] text-muted-foreground mt-0.5">{hint}</div>}
    </div>
  );
}

export default function CadViewer({ preview, validation, height = 480 }: Props) {
  const [interacted, setInteracted] = useState(false);
  const dims = parseDims(preview);
  const kind = classifyPart(preview?.title, preview?.snippet);
  const stressRatio = stressUtil(validation?.fea_max_stress_mpa, validation?.yield_strength_mpa);
  const sf = safetyTone(validation?.safety_factor);

  return (
    <div className="rounded-lg border border-border bg-card/40 overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Mechanical preview
          </div>
          <div className="text-sm font-medium truncate">
            {preview?.title ?? "Untitled part"}
          </div>
        </div>
        <div className="text-[11px] text-muted-foreground font-mono shrink-0">
          {preview?.model_url
            ? preview.model_url.split("/").pop()
            : `${kind} · parametric`}
        </div>
      </div>
      <div
        className="relative bg-linear-to-b from-zinc-950 to-zinc-900"
        style={{ height, background: "linear-gradient(to bottom, #0a0a0d, #18181b)" }}
        onPointerDown={() => setInteracted(true)}
      >
        <Suspense fallback={<LoadingOverlay />}>
          <Canvas
            shadows
            camera={{ position: [3.5, 2.5, 4.5], fov: 38 }}
            dpr={[1, 2]}
            gl={{ antialias: true, alpha: true }}
            style={{ background: "transparent" }}
          >
            <color attach="background" args={["#0a0a0d"]} />
            <fog attach="fog" args={["#0a0a0d", 12, 28]} />
            <Scene preview={preview} validation={validation} />
          </Canvas>
        </Suspense>
        <div className="pointer-events-none absolute top-3 left-3 flex flex-wrap gap-2">
          <Pill label="Bounding box" value={bboxLabel(dims, preview)} />
          {validation?.safety_factor !== undefined && (
            <Pill
              label="Safety factor"
              value={validation.safety_factor.toFixed(2)}
              hint={sf.label}
              color={sf.color}
            />
          )}
          {validation?.fea_max_stress_mpa !== undefined && (
            <Pill
              label="FEA stress"
              value={`${validation.fea_max_stress_mpa} MPa`}
              hint={
                validation.yield_strength_mpa
                  ? `${Math.round((stressRatio ?? 0) * 100)}% of yield`
                  : undefined
              }
              color={
                stressRatio !== null
                  ? `hsl(${Math.round(120 - 120 * stressRatio)}, 70%, 55%)`
                  : undefined
              }
            />
          )}
          {validation?.yield_strength_mpa !== undefined && (
            <Pill label="Yield" value={`${validation.yield_strength_mpa} MPa`} />
          )}
        </div>
        <div className="pointer-events-none absolute bottom-3 right-3 text-[10px] text-muted-foreground font-mono">
          {interacted ? "drag · scroll · pan" : "click to rotate"}
        </div>
      </div>
      {preview?.snippet && (
        <div className="px-4 py-3 text-xs text-muted-foreground border-t border-border">
          {preview.snippet}
        </div>
      )}
    </div>
  );
}

function LoadingOverlay() {
  return (
    <div className="absolute inset-0 grid place-items-center text-xs text-muted-foreground">
      loading model…
    </div>
  );
}
