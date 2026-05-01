import "./styles.css";
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import Plotly from "plotly.js-dist-min";
import * as THREE from "three";

mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" });

const md = new MarkdownIt();
const defaultFence = md.renderer.rules.fence!;
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]!;
  const info = token.info.trim();
  if (info === "mermaid") {
    return `<pre class="mermaid">${md.utils.escapeHtml(token.content)}</pre>\n`;
  }
  return defaultFence(tokens, idx, options, env, self);
};

type Role = "user" | "assistant";

interface UiMessage {
  role: Role;
  content: string;
}

const state: {
  msgs: UiMessage[];
  plotting: THREE.WebGLRenderer | null;
} = { msgs: [], plotting: null };

interface ModelEntry {
  default: string;
  configured: boolean;
}

interface Meta {
  enable_image_gen: boolean;
  primary: string;
  models?: {
    ollama: ModelEntry;
    openai: ModelEntry;
    anthropic: ModelEntry;
  };
}

async function fetchMeta(): Promise<Meta> {
  const r = await fetch("/api/meta");
  const j = await r.json();
  return j as Meta;
}

function renderShell(meta: Meta) {
  const primary = meta.primary || "local";
  document.querySelector("#app")!.innerHTML = `
    <aside class="panel">
      <h1>🌌 Astrophysics AI Lab</h1>
      <p style="color:var(--muted);font-size:0.82rem;margin:0">Hybrid chat (default routing: ${primary}). Pick provider + optional model id.</p>
      <h2>Topics</h2>
      <div id="topics"></div>
    </aside>
    <main class="panel">
      <div class="messages" id="messages"></div>
      <div class="controls">
        <label class="chk"><input type="checkbox" id="use-arxiv" /> Add arXiv context</label>
        <select id="provider" title="LLM backend">
          <option value="auto">Provider: auto</option>
          <option value="ollama">Ollama (local)</option>
          <option value="openai">OpenAI-compatible</option>
          <option value="anthropic">Anthropic</option>
        </select>
        <input type="text" id="model-override" title="Leave empty to use .env default for the selected provider" placeholder="Model id (optional)" style="flex:1;min-width:12rem" />
        <select id="pref" title="When provider is auto: try local Ollama first vs cloud APIs first">
          <option value="auto">Auto routing</option>
          <option value="local">Local first</option>
          <option value="hosted">Hosted first</option>
        </select>
      </div>
      <textarea id="input" placeholder="Ask about stars, cosmology, methods, instruments…"></textarea>
      <div class="controls">
        <button class="primary" id="send">Send</button>
        <button id="clear">Clear chat</button>
      </div>
      <div id="image-row" class="controls" style="display:none">
        <input type="text" id="img-prompt" placeholder="Illustration prompt (optional)" style="flex:1" />
        <button id="img-go">Generate image</button>
      </div>
      <div id="img-out"></div>
    </main>
    <section class="panel">
      <h2>Blackbody curve</h2>
      <label>T (K) <input type="number" id="bb-t" value="5800" min="100" max="50000" step="100" /></label>
      <button id="bb-go" class="primary" style="margin-left:8px">Plot</button>
      <div id="plot-bb"></div>
      <h2>Orbit sketch</h2>
      <div id="orbit-host"></div>
      <p style="color:var(--muted);font-size:0.75rem;margin:0">Schematic WebGL — not to scale.</p>
      <h2>arXiv (astro-ph)</h2>
      <input type="text" id="ax-q" placeholder="Search query (optional)" style="width:100%" />
      <button id="ax-go" class="primary" style="margin-top:6px">Fetch papers</button>
      <div id="papers" style="overflow-y:auto;flex:1;min-height:120px"></div>
    </section>
  `;
}

function wireModelPlaceholder(meta: Meta) {
  const prov = document.getElementById("provider") as HTMLSelectElement | null;
  const inp = document.getElementById("model-override") as HTMLInputElement | null;
  if (!prov || !inp) return;
  const sync = () => {
    const k = prov.value;
    if (k === "auto" || !meta.models) {
      inp.placeholder = "Model id (optional — uses .env per backend)";
      return;
    }
    const m = meta.models[k as keyof typeof meta.models];
    if (!m) return;
    const warn = m.configured ? "" : " — add API key in .env";
    inp.placeholder = `Default: ${m.default}${warn}`;
  };
  prov.addEventListener("change", sync);
  sync();
}

type TopicRow = {
  id: string;
  title: string;
  blurb: string;
  anchors?: string[];
  arxiv_query?: string;
};

async function loadTopics() {
  const r = await fetch("/api/topics");
  const j = await r.json();
  const host = document.getElementById("topics")!;
  host.innerHTML = "";
  for (const t of j.topics as TopicRow[]) {
    const b = document.createElement("button");
    b.className = "topic-btn";
    b.textContent = t.title;
    b.title = t.blurb;
    b.onclick = () => {
      const ta = document.getElementById("input") as HTMLTextAreaElement;
      const axQ = document.getElementById("ax-q") as HTMLInputElement;
      const useArxiv = document.getElementById("use-arxiv") as HTMLInputElement;

      let prompt = `Explain "${t.title}" at a clear undergraduate level. Summarize key ideas, one common misconception, and (if helpful) a small mermaid diagram for relationships between concepts.`;
      if (t.anchors?.length) {
        prompt += ` Touch on these angles when relevant: ${t.anchors.join(", ")}.`;
      }
      if (t.arxiv_query) {
        prompt = `Focus on the arXiv category ${t.arxiv_query} (${t.title}). ${prompt} When citing recent work, align with papers in this category.`;
        axQ.value = t.arxiv_query;
        useArxiv.checked = true;
      } else {
        axQ.value = "";
      }

      ta.value = prompt;
      ta.focus();
    };
    host.appendChild(b);
  }
}

function renderMessages() {
  const el = document.getElementById("messages")!;
  el.innerHTML = "";
  for (const m of state.msgs) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${m.role}`;
    const body = document.createElement("div");
    body.className = "body";
    if (m.role === "assistant") {
      body.innerHTML = md.render(m.content);
    } else {
      body.textContent = m.content;
    }
    wrap.appendChild(body);
    el.appendChild(wrap);
  }
  el.querySelectorAll(".mermaid").forEach(() => {});
  void mermaid.run({ querySelector: "#messages .mermaid" });
  el.scrollTop = el.scrollHeight;
}

async function streamChat() {
  const input = document.getElementById("input") as HTMLTextAreaElement;
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  state.msgs.push({ role: "user", content: text });
  state.msgs.push({ role: "assistant", content: "" });
  renderMessages();

  const sendBtn = document.getElementById("send") as HTMLButtonElement;
  sendBtn.disabled = true;

  const preference = (document.getElementById("pref") as HTMLSelectElement).value;
  const provider = (document.getElementById("provider") as HTMLSelectElement).value;
  const modelRaw = (document.getElementById("model-override") as HTMLInputElement).value.trim();
  const use_arxiv = (document.getElementById("use-arxiv") as HTMLInputElement).checked;

  const payload = {
    messages: state.msgs.filter((m) => m.role === "user" || (m.role === "assistant" && m.content)).map((m) => ({
      role: m.role,
      content: m.content,
    })),
    preference,
    provider,
    model: modelRaw || null,
    use_arxiv,
  };

  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    state.msgs[state.msgs.length - 1]!.content = `**Error** ${res.status}`;
    renderMessages();
    sendBtn.disabled = false;
    return;
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const block of parts) {
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const payloadText = line.slice(6).trim();
          if (payloadText === "[DONE]") continue;
          let data: Record<string, string>;
          try {
            data = JSON.parse(payloadText) as Record<string, string>;
          } catch {
            continue;
          }
          if (data.error) {
            state.msgs[state.msgs.length - 1]!.content = `**Error** ${data.error}`;
          } else if (data.token) {
            state.msgs[state.msgs.length - 1]!.content += data.token;
            const msgsEl = document.getElementById("messages")!;
            const lastBody = msgsEl.querySelector(".msg.assistant:last-child .body") as HTMLElement | null;
            if (lastBody) {
              lastBody.innerHTML = md.render(state.msgs[state.msgs.length - 1]!.content);
              void mermaid.run({ querySelector: "#messages .mermaid:last-of-type" });
            }
          }
          msgsElScroll();
        }
      }
    }
  } finally {
    sendBtn.disabled = false;
  }
  renderMessages();
}

function msgsElScroll() {
  const msgsEl = document.getElementById("messages")!;
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

async function plotBlackbody() {
  const tEl = document.getElementById("bb-t") as HTMLInputElement;
  const T = Number(tEl.value) || 5800;
  const r = await fetch(`/api/viz/blackbody?t=${encodeURIComponent(String(T))}`);
  const fig = await r.json();
  const data = Array.isArray(fig.data) ? fig.data : [];
  const layout = fig.layout || {};
  await Plotly.react("plot-bb", data, layout, { responsive: true, displaylogo: false });
}

interface BodySpec {
  name: string;
  color: string;
  radius: number;
  orbitRadius: number;
  speed: number;
}

async function setupOrbit() {
  const host = document.getElementById("orbit-host")!;
  const r = await fetch("/api/viz/orbit-spec");
  const spec = (await r.json()) as { bodies: BodySpec[] };

  while (host.firstChild) host.removeChild(host.firstChild);
  if (state.plotting) {
    state.plotting.dispose();
    state.plotting = null;
  }

  const w = host.clientWidth || 320;
  const h = host.clientHeight || 240;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  host.appendChild(renderer.domElement);
  state.plotting = renderer;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
  camera.position.set(0, 2.4, 3.2);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const dir = new THREE.DirectionalLight(0xffffff, 1.1);
  dir.position.set(2, 4, 2);
  scene.add(dir);

  const meshes: { mesh: THREE.Mesh; orbitRadius: number; speed: number; phase: number }[] = [];
  for (const b of spec.bodies) {
    const geom = new THREE.SphereGeometry(b.radius, 24, 24);
    const mat = new THREE.MeshStandardMaterial({ color: b.color, emissive: b.color, emissiveIntensity: b.name === "star" ? 0.6 : 0.05 });
    const mesh = new THREE.Mesh(geom, mat);
    scene.add(mesh);
    meshes.push({ mesh, orbitRadius: b.orbitRadius, speed: b.speed, phase: Math.random() * Math.PI * 2 });
  }

  let t0 = performance.now();
  function frame(now: number) {
    const t = (now - t0) * 0.001;
    for (const m of meshes) {
      const a = m.phase + t * m.speed;
      m.mesh.position.set(Math.cos(a) * m.orbitRadius, 0, Math.sin(a) * m.orbitRadius);
    }
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.addEventListener(
    "resize",
    () => {
      const nw = host.clientWidth;
      const nh = host.clientHeight;
      if (nw && nh) {
        renderer.setSize(nw, nh);
        camera.aspect = nw / nh;
        camera.updateProjectionMatrix();
      }
    },
    { passive: true },
  );
}

async function loadPapers() {
  const q = (document.getElementById("ax-q") as HTMLInputElement).value.trim();
  const host = document.getElementById("papers")!;
  host.textContent = "Loading…";
  const r = await fetch(`/api/arxiv/papers?q=${encodeURIComponent(q)}&limit=8`);
  const j = await r.json();
  host.innerHTML = "";
  for (const p of j.papers as { arxiv_id: string; title: string; authors: string; pdf_url: string }[]) {
    const d = document.createElement("div");
    d.className = "paper";
    const link = p.pdf_url ? `<a href="${p.pdf_url}" target="_blank" rel="noreferrer">PDF</a>` : "";
    d.innerHTML = `<strong>${p.title}</strong><br/><span>${p.authors}</span> · ${link} · <code>${p.arxiv_id}</code>`;
    host.appendChild(d);
  }
}

async function genImage() {
  const prompt = (document.getElementById("img-prompt") as HTMLInputElement).value.trim();
  if (!prompt) return;
  const out = document.getElementById("img-out")!;
  out.textContent = "Generating…";
  const r = await fetch("/api/image/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  const j = await r.json();
  if (!r.ok) {
    out.textContent = typeof j.detail === "string" ? j.detail : JSON.stringify(j);
    return;
  }
  const url = j.urls?.[0];
  if (url?.startsWith("http")) {
    out.innerHTML = `<img alt="" src="${url}" style="max-width:100%;border-radius:10px;border:1px solid var(--border)" />`;
    if (j.revised_prompt) out.innerHTML += `<p style="color:var(--muted);font-size:0.78rem">${j.revised_prompt}</p>`;
  } else {
    out.textContent = JSON.stringify(j);
  }
}

async function boot() {
  const meta = await fetchMeta().catch(
    (): Meta => ({
      enable_image_gen: false,
      primary: "local",
      models: {
        ollama: { default: "llama3.2", configured: true },
        openai: { default: "gpt-4o-mini", configured: false },
        anthropic: { default: "claude-3-5-sonnet-20241022", configured: false },
      },
    }),
  );
  renderShell(meta);
  wireModelPlaceholder(meta);
  await loadTopics();
  document.getElementById("send")!.onclick = () => void streamChat();
  document.getElementById("clear")!.onclick = () => {
    state.msgs = [];
    renderMessages();
  };
  document.getElementById("input")!.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void streamChat();
    }
  });
  if (meta.enable_image_gen) {
    (document.getElementById("image-row") as HTMLElement).style.display = "flex";
    document.getElementById("img-go")!.onclick = () => void genImage();
  }
  document.getElementById("bb-go")!.onclick = () => void plotBlackbody();
  document.getElementById("ax-go")!.onclick = () => void loadPapers();
  await plotBlackbody().catch(() => {});
  await setupOrbit().catch((e) => console.error(e));
}

void boot();
