const dagList = document.getElementById("dag-list");
const dagSearch = document.getElementById("dag-search");
const statusFilter = document.getElementById("status-filter");
const sourcePaths = document.getElementById("source-paths");
const dagInput = document.getElementById("dag-input");
const dagRefresh = document.getElementById("dag-refresh");
const sourceInput = document.getElementById("source-input");
const pdfsInput = document.getElementById("pdfs-input");
const outputInput = document.getElementById("output-input");
const projectInput = document.getElementById("project-input");
const timeline = document.getElementById("timeline");
const activityFeed = document.getElementById("activity-feed");
const dagSummary = document.getElementById("dag-summary");
const dagWarnings = document.getElementById("dag-warnings");
const workflowName = document.getElementById("workflow-name");
const outputPath = document.getElementById("output-path");
const copyPathBtn = document.getElementById("copy-path");
const openFolder = document.getElementById("open-folder");
const artifactList = document.getElementById("artifact-list");
const artifactPreview = document.getElementById("artifact-preview");
const exportDagBtn = document.getElementById("export-dag");
const migrateBtn = document.getElementById("migrate-btn");
const settingsBtn = document.getElementById("settings-btn");
const settingsDrawer = document.getElementById("settings-drawer");
const closeSettings = document.getElementById("close-settings");
const pdfPreview = document.getElementById("pdf-preview");
const pdfReload = document.getElementById("pdf-reload");
const cursorTest = document.getElementById("cursor-test");
const inhouseTest = document.getElementById("inhouse-test");
const agentMode = document.getElementById("agent-mode");
const cursorKey = document.getElementById("cursor-key");
const cursorRepo = document.getElementById("cursor-repo");
const cursorRef = document.getElementById("cursor-ref");
const inhouseUrl = document.getElementById("inhouse-url");
const inhouseToken = document.getElementById("inhouse-token");
const inhouseModel = document.getElementById("inhouse-model");
const inhouseHeaders = document.getElementById("inhouse-headers");
const groqKey = document.getElementById("groq-key");
const groqModel = document.getElementById("groq-model");
const openrouterKey = document.getElementById("openrouter-key");
const openrouterModel = document.getElementById("openrouter-model");
const groqTest = document.getElementById("groq-test");
const openrouterTest = document.getElementById("openrouter-test");
const noInference = document.getElementById("no-inference");
const pdfRequired = document.getElementById("pdf-required");

let session = null;
let activity = [];
let selectedDag = null;
let selectedDags = new Set();
let sessionError = null;
let allowedAgents = [];

const stageMap = {
  "Not Started": "not-started",
  "In Progress": "in-progress",
  "Needs Review": "needs-review",
  "Migrated": "migrated",
  "Failed": "failed",
};

async function loadSession() {
  try {
    const response = await fetch("/api/session");
    if (response.ok) {
      const data = await response.json();
      allowedAgents = Array.isArray(data.allowed_agents) ? data.allowed_agents : [];
      sessionError = null;
      return data;
    }
  } catch (err) {
    // fallback to local session.json
  }
  try {
    const response = await fetch("./session.json");
    const data = await response.json();
    allowedAgents = Array.isArray(data.allowed_agents) ? data.allowed_agents : [];
    sessionError = null;
    return data;
  } catch (err) {
    sessionError = "Unable to load session data. Is the UI server running?";
    return {
      migration_root: "",
      source_inputs: [],
      agent_mode: "inhouse",
      agent_configured: false,
      dags: [],
      timeline: ["Scan", "Index", "Analyze", "Plan", "Generate", "Validate", "Done"],
    };
  }
}

function parseSourceInputs() {
  const extra = sourceInput.value
    .split(/\n|,/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
  const dagPath = (dagInput?.value || "").trim();
  if (dagPath) {
    const combined = [dagPath, ...extra];
    return Array.from(new Set(combined));
  }
  return extra;
}

async function loadActivity() {
  try {
    const response = await fetch("/api/activity");
    if (response.ok) {
      const data = await response.json();
      return Array.isArray(data) ? data : [];
    }
    const fallback = await fetch("./activity.json");
    const data = await fallback.json();
    return Array.isArray(data) ? data : [];
  } catch (err) {
    return [];
  }
}

function renderTimeline(stages) {
  timeline.innerHTML = "";
  const activityStages = new Set(activity.map((event) => event.event));
  const completedStages = [];
  stages.forEach((stage) => {
    if (activityStages.has(stage)) {
      completedStages.push(stage);
    }
  });
  const activeStage = completedStages[completedStages.length - 1];
  stages.forEach((stage) => {
    const item = document.createElement("div");
    const isDone = completedStages.includes(stage);
    const isActive = stage === activeStage;
    item.className = `phase${isDone ? " done" : ""}${isActive ? " active" : ""}`;
    item.textContent = stage;
    timeline.appendChild(item);
  });
}

function renderDagList() {
  const dags = session?.dags || [];
  const searchValue = dagSearch.value.toLowerCase();
  const statusValue = statusFilter.value;
  dagList.innerHTML = "";
  if (dags.length === 0) {
    const item = document.createElement("li");
    item.className = "dag-empty";
    item.textContent = sessionError || "No DAGs found. Check the source path.";
    dagList.appendChild(item);
    return;
  }
  const filtered = dags
    .filter((dag) => dag.dag_id.toLowerCase().includes(searchValue))
    .filter((dag) => statusValue === "all" || dag.status === statusValue);

  if (filtered.length === 0 && statusValue !== "all") {
    statusFilter.value = "all";
    return renderDagList();
  }

  if (filtered.length === 0) {
    const item = document.createElement("li");
    item.className = "dag-empty";
    item.textContent = "No DAGs match the current filters.";
    dagList.appendChild(item);
    return;
  }

  filtered
    .forEach((dag) => {
      const item = document.createElement("li");
      item.className = `dag-item ${selectedDag?.dag_id === dag.dag_id ? "active" : ""}`;
      const badgeClass = stageMap[dag.status] || "not-started";
      const checked = selectedDags.has(dag.dag_id) ? "checked" : "";
      item.innerHTML = `
        <div class="dag-row">
          <input type="checkbox" class="dag-select" data-dag="${dag.dag_id}" ${checked} />
          <strong>${dag.dag_id}</strong>
          <span class="badge ${badgeClass}">${dag.status}</span>
        </div>
        <div class="dag-meta">tasks: ${dag.task_count} • schedule: ${dag.schedule || "n/a"}</div>
      `;
      item.addEventListener("click", () => selectDag(dag));
      dagList.appendChild(item);
    });

  dagList.querySelectorAll(".dag-select").forEach((checkbox) => {
    checkbox.addEventListener("click", (event) => {
      event.stopPropagation();
      const dagId = checkbox.getAttribute("data-dag");
      if (!dagId) return;
      if (checkbox.checked) {
        selectedDags.add(dagId);
      } else {
        selectedDags.delete(dagId);
      }
    });
  });
}

function selectDag(dag) {
  selectedDag = dag;
  renderDagList();
  renderDagSummary();
  renderArtifacts();
  renderActivity();
  loadPdfPreview();
}

function renderDagSummary() {
  if (!selectedDag) return;
  dagSummary.innerHTML = `
    <div>Schedule: ${selectedDag.schedule || "n/a"}</div>
    <div>Tasks: ${selectedDag.task_count}</div>
    <div>Unknown operators: ${selectedDag.unknown_operator_count}</div>
  `;
  dagWarnings.innerHTML =
    selectedDag.status === "Needs Review"
      ? "Needs review: some tasks could not be confidently mapped."
      : "";
  workflowName.textContent = `${selectedDag.dag_id}_job`;
  outputPath.textContent = session.migration_root;
  openFolder.href = `file://${session.migration_root}`;
  exportDagBtn.href = `./${selectedDag.dag_id}/export_bundle.zip`;
}

function renderArtifacts() {
  if (!selectedDag) return;
  artifactList.innerHTML = "";
  const artifacts = [
    "databricks.yml",
    `notebooks/${selectedDag.dag_id}/`,
    "utils/",
    `reports/${selectedDag.dag_id}/migration_plan.md`,
    `reports/${selectedDag.dag_id}/task_mapping.json`,
    `reports/${selectedDag.dag_id}/assumptions.md`,
    `reports/${selectedDag.dag_id}/validation_report.md`,
    `reports/${selectedDag.dag_id}/task_graph.json`,
    `reports/${selectedDag.dag_id}/code_index.json`,
  ];
  artifacts.forEach((artifact) => {
    const li = document.createElement("li");
    li.textContent = artifact;
    li.addEventListener("click", () => previewArtifact(artifact));
    artifactList.appendChild(li);
  });
}

async function previewArtifact(artifact) {
  if (artifact.endsWith("/")) {
    artifactPreview.textContent = "Select a specific file to preview.";
    return;
  }
  const normalized = artifact.replace("reports/", "");
  const path =
    artifact === "databricks.yml"
      ? "../databricks.yml"
      : `../${artifact}`;
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error("not found");
    artifactPreview.textContent = await response.text();
  } catch (error) {
    artifactPreview.textContent = `Unable to load ${normalized}.`;
  }
}

function renderActivity() {
  activityFeed.innerHTML = "";
  activity
    .filter((event) => !selectedDag || !event.dag_id || event.dag_id === selectedDag.dag_id)
    .slice(-20)
    .reverse()
    .forEach((event) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${event.event}</strong> — ${event.detail}`;
      activityFeed.appendChild(li);
    });
}

function updateMigrateButton() {
  migrateBtn.disabled = !session || !session.agent_configured;
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) return {};
    return response.json();
  } catch (err) {
    return {};
  }
}

function applyAllowedAgents() {
  const restricted = Array.isArray(allowedAgents) && allowedAgents.length > 0;
  const allowedSet = new Set(allowedAgents);
  Array.from(agentMode.options).forEach((option) => {
    if (!restricted) {
      option.hidden = false;
      option.disabled = false;
      return;
    }
    const keep = allowedSet.has(option.value);
    option.hidden = !keep;
    option.disabled = !keep;
  });
  document.querySelectorAll(".drawer-section[data-agent]").forEach((section) => {
    if (!restricted) {
      section.classList.remove("hidden");
      return;
    }
    const agent = section.getAttribute("data-agent");
    if (agent && allowedSet.has(agent)) {
      section.classList.remove("hidden");
    } else {
      section.classList.add("hidden");
    }
  });
  if (restricted && agentMode.value && !allowedSet.has(agentMode.value)) {
    agentMode.value = allowedAgents[0];
  }
}

async function saveSettings() {
  const payload = {
    agent_mode: agentMode.value,
    cursor_api_key: cursorKey.value,
    cursor_repository: cursorRepo.value,
    cursor_ref: cursorRef.value,
    inhouse_agent_url: inhouseUrl.value,
    inhouse_api_key: inhouseToken.value,
    inhouse_model: inhouseModel.value,
    inhouse_headers_json: inhouseHeaders.value,
    groq_api_key: groqKey.value,
    groq_model: groqModel.value,
    openrouter_api_key: openrouterKey.value,
    openrouter_model: openrouterModel.value,
    source_inputs: parseSourceInputs(),
    pdfs_path: pdfsInput.value || undefined,
    output_root: outputInput.value || undefined,
    project_name: projectInput.value || undefined,
    selected_dags: Array.from(selectedDags),
    no_inference: noInference.checked,
    pdf_required: pdfRequired.checked,
  };
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function testConnection(mode) {
  await saveSettings();
  const response = await fetch("/api/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  const result = await response.json();
  alert(result.ok ? "Connection OK" : `Connection failed: ${result.error}`);
}

async function migrate() {
  await saveSettings();
  const response = await fetch("/api/migrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inputs: parseSourceInputs(),
      pdfs_path: pdfsInput.value || undefined,
      output_root: outputInput.value,
      project_name: projectInput.value || "airflow-migration",
      notebook_format: "py",
      agent_mode: agentMode.value,
      selected_dags: Array.from(selectedDags),
    }),
  });
  const result = await response.json();
  if (!result.ok) {
    alert(result.error || "Migration failed");
  }
}

async function loadPdfPreview() {
  if (!pdfPreview) return;
  if (!selectedDag) {
    pdfPreview.textContent = "Select a DAG to preview its PDF.";
    return;
  }
  const response = await fetch(
    `/api/pdf_text?dag_id=${encodeURIComponent(selectedDag.dag_id)}`
  );
  if (!response.ok) {
    pdfPreview.textContent = "Unable to load PDF preview.";
    return;
  }
  const result = await response.json();
  if (result.ok) {
    pdfPreview.textContent = result.text || "(empty)";
  } else {
    const error = result.error || "pdf_not_found";
    pdfPreview.textContent = `PDF not available (${error}).`;
  }
}

async function refreshDags() {
  await saveSettings();
  const response = await fetch("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inputs: parseSourceInputs(),
    }),
  });
  if (!response.ok) {
    const result = await response.json();
    alert(result.error || "Failed to refresh DAGs");
    return;
  }
  session = await response.json();
  renderTimeline(session?.timeline || []);
  sourcePaths.textContent = (session.source_inputs || []).join(", ") || "—";
  renderDagList();
  const dags = session?.dags || [];
  if (dags.length > 0) {
    selectDag(dags[0]);
  }
  updateMigrateButton();
}

function setupHandlers() {
  dagSearch.addEventListener("input", renderDagList);
  statusFilter.addEventListener("change", renderDagList);
  copyPathBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(session.migration_root);
  });
  if (pdfReload) {
    pdfReload.addEventListener("click", loadPdfPreview);
  }
  if (dagRefresh) {
    dagRefresh.addEventListener("click", refreshDags);
  }
  settingsBtn.addEventListener("click", () => settingsDrawer.classList.remove("hidden"));
  closeSettings.addEventListener("click", () => settingsDrawer.classList.add("hidden"));
  cursorTest.addEventListener("click", () => testConnection("cursor"));
  inhouseTest.addEventListener("click", () => testConnection("inhouse"));
  groqTest.addEventListener("click", () => testConnection("groq"));
  openrouterTest.addEventListener("click", () => testConnection("openrouter"));
  migrateBtn.addEventListener("click", migrate);
}

async function poll() {
  session = await loadSession();
  activity = await loadActivity();
  sourcePaths.textContent = (session.source_inputs || []).join(", ") || "—";
  renderTimeline(session?.timeline || []);
  renderDagList();
  applyAllowedAgents();
  const dags = session?.dags || [];
  if (!selectedDag && dags.length > 0) {
    selectDag(dags[0]);
  } else {
    renderDagSummary();
    renderArtifacts();
    renderActivity();
  }
  updateMigrateButton();
}

async function init() {
  session = await loadSession();
  activity = await loadActivity();
  renderTimeline(session?.timeline || []);
  sourcePaths.textContent = (session.source_inputs || []).join(", ") || "—";
  const settings = await loadSettings();
  if ((!allowedAgents || allowedAgents.length === 0) && Array.isArray(settings.allowed_agents)) {
    allowedAgents = settings.allowed_agents;
  }
  agentMode.value = settings.agent_mode || "inhouse";
  cursorKey.value = settings.cursor_api_key || "";
  cursorRepo.value = settings.cursor_repository || "";
  cursorRef.value = settings.cursor_ref || "";
  inhouseUrl.value = settings.inhouse_agent_url || "";
  inhouseToken.value = settings.inhouse_api_key || "";
  inhouseModel.value = settings.inhouse_model || "";
  inhouseHeaders.value = settings.inhouse_headers_json || "";
  groqKey.value = settings.groq_api_key || "";
  groqModel.value = settings.groq_model || "";
  openrouterKey.value = settings.openrouter_api_key || "";
  openrouterModel.value = settings.openrouter_model || "";
  if (dagInput) {
    dagInput.value = "";
  }
  sourceInput.value = (settings.source_inputs || []).join("\n");
  pdfsInput.value = settings.pdfs_path || "";
  outputInput.value = settings.output_root || "";
  projectInput.value = settings.project_name || "";
  selectedDags = new Set(settings.selected_dags || []);
  noInference.checked = Boolean(settings.no_inference);
  pdfRequired.checked = Boolean(settings.pdf_required);
  renderDagList();
  const dags = session?.dags || [];
  if (dags.length > 0) {
    selectDag(dags[0]);
  }
  updateMigrateButton();
  applyAllowedAgents();
  setupHandlers();
  setInterval(poll, 4000);
}

init();
