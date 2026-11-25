// chart.js — Salary distribution bar rendered from data attributes

(function () {
  const bar = document.getElementById("salaryBar");
  if (!bar) return;

  const current   = parseInt(bar.dataset.current,   10);
  const p25       = parseInt(bar.dataset.p25,       10);
  const median    = parseInt(bar.dataset.median,    10);
  const p75       = parseInt(bar.dataset.p75,       10);
  const p90       = parseInt(bar.dataset.p90,       10);
  const potential = parseInt(bar.dataset.potential, 10);

  const allVals = [current, p25, median, p75, p90, potential].filter(Boolean);
  const min = Math.min(...allVals) * 0.86;
  const max = Math.max(...allVals) * 1.08;

  const pct = (v) => Math.max(1, Math.min(99, ((v - min) / (max - min)) * 100));
  const fmtK = (v) => "$" + Math.round(v / 1000) + "K";

  // Build the HTML for the chart
  let html = `
    <div style="position:relative; height:80px; width:100%; padding-top:32px;">
      <!-- Track -->
      <div style="position:absolute; top:44px; left:0; right:0; height:8px;
                  background:#F3F4F6; border-radius:4px;"></div>

      <!-- Market range fill (p25–p90) -->
      <div style="position:absolute; top:44px;
                  left:${pct(p25)}%;
                  width:${pct(p90) - pct(p25)}%;
                  height:8px;
                  background:linear-gradient(90deg, #9FE1CB 0%, #5DCAA5 100%);
                  border-radius:4px; opacity:0.55;"></div>
  `;

  // Tick marks for p25, median, p75, p90
  const ticks = [
    { val: p25,    label: "25th" },
    { val: median, label: "Median" },
    { val: p75,    label: "75th" },
    { val: p90,    label: "90th" },
  ];

  ticks.forEach(({ val, label }) => {
    const left = pct(val);
    html += `
      <div style="position:absolute; top:42px; left:${left}%;
                  transform:translateX(-50%); width:2px; height:12px;
                  background:#D1D5DB;"></div>
      <div style="position:absolute; top:58px; left:${left}%;
                  transform:translateX(-50%); text-align:center; white-space:nowrap;">
        <span style="font-size:11px; color:#9CA3AF; line-height:1.3;">
          ${label}<br>
          <strong style="color:#6B7280;">${fmtK(val)}</strong>
        </span>
      </div>
    `;
  });

  // Current salary needle (amber)
  const curLeft = pct(current);
  html += `
    <div style="position:absolute; left:${curLeft}%; top:8px; transform:translateX(-50%);">
      <div style="background:#BA7517; color:white; font-size:11px; font-weight:600;
                  padding:2px 7px; border-radius:4px; white-space:nowrap; margin-bottom:3px;
                  text-align:center;">
        You · ${fmtK(current)}
      </div>
      <div style="width:3px; height:26px; background:#BA7517; margin:0 auto; border-radius:2px;"></div>
    </div>
  `;

  // Potential salary needle (green)
  if (potential && potential > current) {
    const potLeft = pct(potential);
    html += `
      <div style="position:absolute; left:${potLeft}%; top:8px; transform:translateX(-50%);">
        <div style="background:#1D9E75; color:white; font-size:11px; font-weight:600;
                    padding:2px 7px; border-radius:4px; white-space:nowrap; margin-bottom:3px;
                    text-align:center;">
          Target · ${fmtK(potential)}
        </div>
        <div style="width:3px; height:26px; background:#1D9E75; margin:0 auto; border-radius:2px;"></div>
      </div>
    `;
  }

  html += `</div>`;
  bar.innerHTML = html;
})();
