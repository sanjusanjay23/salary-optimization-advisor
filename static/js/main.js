// main.js — Form interactions, file upload preview, loading overlay

// ── File upload UI ──────────────────────────────────────────────────────
const dropzone    = document.getElementById("dropzone");
const fileInput   = document.getElementById("resume");
const filePreview = document.getElementById("filePreview");
const dropzoneInner = document.getElementById("dropzoneInner");
const fileName    = document.getElementById("fileName");
const fileSize    = document.getElementById("fileSize");
const fileRemove  = document.getElementById("fileRemove");

function showFile(file) {
  if (!file) return;
  if (file.type !== "application/pdf") {
    alert("Only PDF files are accepted.");
    fileInput.value = "";
    return;
  }
  const sizeMB = (file.size / 1024 / 1024).toFixed(2);
  if (file.size > 20 * 1024 * 1024) {
    alert("File must be under 20MB.");
    fileInput.value = "";
    return;
  }
  fileName.textContent = file.name;
  fileSize.textContent = `${(file.size / 1024).toFixed(0)} KB  ·  Click × to remove`;
  dropzoneInner.style.display = "none";
  filePreview.style.display   = "flex";
}

fileInput.addEventListener("change", (e) => showFile(e.target.files[0]));

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) {
    // Create a DataTransfer to assign to file input
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    showFile(file);
  }
});

if (fileRemove) {
  fileRemove.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.value = "";
    filePreview.style.display   = "none";
    dropzoneInner.style.display = "block";
  });
}

// ── Loading overlay ──────────────────────────────────────────────────────
const overlay    = document.getElementById("loadingOverlay");
const loadingMsg = document.getElementById("loadingMsg");
const form       = document.getElementById("analyzeForm");
const submitBtn  = document.getElementById("submitBtn");

const LOADING_STEPS = [
  { id: "ls1", msg: "Parsing your resume with PyPDF2..." },
  { id: "ls2", msg: "Fetching official BLS salary data..." },
  { id: "ls3", msg: "Running AI analysis..." },
  { id: "ls4", msg: "Building your personalized report..." },
];

let stepIdx = 0;

function advanceStep() {
  if (stepIdx < LOADING_STEPS.length) {
    const s = LOADING_STEPS[stepIdx];

    // Mark previous step done
    if (stepIdx > 0) {
      const prevDot = document.querySelector(`#${LOADING_STEPS[stepIdx-1].id} .lstep-dot`);
      if (prevDot) { prevDot.classList.remove("active"); prevDot.classList.add("done"); }
    }

    // Activate current
    const dot = document.querySelector(`#${s.id} .lstep-dot`);
    if (dot) dot.classList.add("active");
    loadingMsg.textContent = s.msg;
    stepIdx++;
  }
}

form.addEventListener("submit", (e) => {
  // Basic client-side validation
  const jobTitle = document.getElementById("job_title").value.trim();
  const salary   = document.getElementById("current_salary").value.trim();
  const location = document.getElementById("location").value.trim();

  if (!jobTitle || !salary || !location) return; // let HTML5 required handle it

  // Show overlay
  overlay.style.display = "flex";
  submitBtn.disabled    = true;

  // Step through loading messages
  advanceStep(); // step 1 immediately
  setTimeout(advanceStep, 4000);  // step 2 at 4s
  setTimeout(advanceStep, 12000); // step 3 at 12s
  setTimeout(advanceStep, 22000); // step 4 at 22s
});

// ── Salary formatting ────────────────────────────────────────────────────
const salaryInput = document.getElementById("current_salary");
if (salaryInput) {
  salaryInput.addEventListener("blur", () => {
    const raw = salaryInput.value.replace(/[^0-9]/g, "");
    if (raw) {
      salaryInput.value = parseInt(raw, 10).toLocaleString();
    }
  });
  salaryInput.addEventListener("focus", () => {
    salaryInput.value = salaryInput.value.replace(/,/g, "");
  });
}
