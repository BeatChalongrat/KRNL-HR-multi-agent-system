// ---------- helpers ----------
async function j(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let t; try { t = await r.text(); } catch { t = r.statusText; }
    throw new Error(t || `HTTP ${r.status}`);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/json") ? r.json() : r.text();
}

function badge(s) {
  if (s === "COMPLETED") return `<span class="badge badge-ok">COMPLETED</span>`;
  if (s === "RUNNING")   return `<span class="badge badge-run">RUNNING</span>`;
  if (s === "FAILED")    return `<span class="badge badge-fail">FAILED</span>`;
  if (s === "PENDING")   return `<span class="badge badge-pending">PENDING</span>`;
  return `<span class="badge">${s || "-"}</span>`;
}

function btnLoading(btn, on, text = "…") {
  if (!btn) return;
  if (on) { btn.dataset.prev = btn.textContent; btn.textContent = text; btn.disabled = true; }
  else    { btn.textContent = btn.dataset.prev || btn.textContent; btn.disabled = false; }
}

// ---------- table ----------
async function loadEmployees() {
  const tb = document.querySelector("#tblEmployees tbody");
  tb.innerHTML = `<tr><td colspan="8" style="opacity:.7">Loading…</td></tr>`;
  let data = [];
  try { data = await j("/api/employees"); }
  catch (e) { alert("Load employees failed: " + e.message); tb.innerHTML = ""; return; }

  tb.innerHTML = "";
  if (!Array.isArray(data) || data.length === 0) {
    tb.innerHTML = `<tr><td colspan="8" style="opacity:.6">No employees yet</td></tr>`;
    return;
  }

  for (const e of data) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${e.id}</td>
      <td>${e.name}</td>
      <td>${e.email}</td>
      <td>${e.role}</td>
      <td>${e.department || "-"}</td>
      <td>${e.start_date}</td>
      <td>${badge(e.status)}</td>
      <td class="actions">
        <button class="btn-secondary run"  data-id="${e.id}">Run</button>
        <button class="btn-secondary logs" data-id="${e.id}">Logs</button>
        <button class="btn-danger delete" data-id="${e.id}">Delete</button>
      </td>`;
    tb.appendChild(tr);
  }
}

// ---------- add form ----------
async function onSubmitNew(ev) {
  ev.preventDefault();
  const f = ev.target;
  const fd = new FormData(f);
  const btn = document.getElementById("btnAdd");

  for (const k of ["name","email","role","start_date"]) {
    if (!(fd.get(k) || "").toString().trim()) {
      alert(`Please enter ${k}`);
      return;
    }
  }

  try {
    btnLoading(btn, true);
    await j("/api/employees", { method: "POST", body: fd });
    f.reset();
    await loadEmployees();
  } catch (e) {
    alert("Add failed: " + e.message);
  } finally {
    btnLoading(btn, false);
  }
}

// ---------- upload CSV ----------
async function uploadCsv() {
  const input = document.getElementById("csvFile");
  if (!input.files || !input.files[0]) {
    alert("Please select a CSV file first.");
    return;
  }
  const btn = document.getElementById("btnUploadCsv");
  btnLoading(btn, true);
  try {
    const fd = new FormData();
    fd.append("file", input.files[0]);
    const res = await j("/api/employees/upload_csv", { method: "POST", body: fd });
    const s = res.summary || {};
    alert(`CSV result:\n- Inserted: ${s.inserted || 0}\n- Skipped: ${s.skipped || 0}\n- Errors: ${s.errors || 0}`);
    input.value = "";
    await loadEmployees();
  } catch (e) {
    alert("Upload failed: " + e.message);
  } finally {
    btnLoading(btn, false);
  }
}

// ---------- table actions ----------
function bindTableActions() {
  const tb = document.querySelector("#tblEmployees tbody");
  tb.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    const id = btn.dataset.id;

    // Run
    if (btn.classList.contains("run")) {
      try {
        // show RUNNING immediately
        const row = btn.closest("tr");
        if (row) row.children[6].innerHTML = badge("RUNNING");

        btnLoading(btn, true);
        await j(`/api/run/${id}`, { method: "POST" });
        await loadEmployees();
      } catch (e) {
        alert("Run failed: " + e.message);
        await loadEmployees();
      } finally {
        btnLoading(btn, false, "Run");
      }
      return;
    }

    // Logs
    if (btn.classList.contains("logs")) {
      try {
        const logs = await j(`/api/logs/${id}`);
        const panel = document.getElementById("logsPanel");
        document.getElementById("logsBox").textContent = JSON.stringify(logs, null, 2);
        panel.style.display = "block";
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (e) { alert("Load logs failed: " + e.message); }
      return;
    }

    // Delete
    if (btn.classList.contains("delete")) {
      if (!confirm("Delete this employee and related logs?")) return;
      try {
        btnLoading(btn, true);
        await fetch(`/api/employees/${id}`, { method: "DELETE" });
        await loadEmployees();
      } catch (e) {
        alert("Delete failed: " + e.message);
      } finally {
        btnLoading(btn, false, "Delete");
      }
      return;
    }
  });
}

// ---------- logs panel close ----------
function bindLogsPanel() {
  const closeBtn = document.getElementById("btnCloseLogs");
  const panel = document.getElementById("logsPanel");
  closeBtn.addEventListener("click", () => {
    document.getElementById("logsBox").textContent = "";
    panel.style.display = "none";
  });
}

// ---------- bootstrap ----------
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("frmNew")?.addEventListener("submit", onSubmitNew);
  document.getElementById("btnUploadCsv")?.addEventListener("click", uploadCsv);
  bindTableActions();
  bindLogsPanel();
  loadEmployees();
});
