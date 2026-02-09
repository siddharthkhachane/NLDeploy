let currentSpec = null;
let currentSpecType = null;
let isDeploying = false;
let currentPreview = null;

const DEPLOY_STAGES = ["parse", "plan", "canary", "rollout", "verify", "rollback", "failed"];
const COMMAND_STAGES = ["parse", "plan", "execute", "verify", "blocked", "failed"];

function stageList() {
    return currentSpecType === "command" ? COMMAND_STAGES : DEPLOY_STAGES;
}

function renderTimeline(activeStage = "parse") {
    const panel = document.getElementById("timelinePanel");
    const stages = stageList();
    panel.innerHTML = stages
        .map((stage) => {
            const cls = stage === activeStage ? "stage active" : "stage";
            return `<div class="${cls}">${stage}</div>`;
        })
        .join("");
}

async function pollNodes() {
    try {
        const response = await fetch("/api/nodes");
        const nodes = await response.json();
        renderNodes(nodes);
    } catch (error) {
        console.error("Error polling nodes:", error);
    }
}

function renderNodes(nodes) {
    const panel = document.getElementById("nodesPanel");
    if (!nodes || nodes.length === 0) {
        panel.innerHTML = '<div class="loading">No nodes available</div>';
        return;
    }

    panel.innerHTML = nodes
        .map(
            (node) => `
            <div class="node-card ${node.healthy ? "healthy" : "unhealthy"}">
                <div class="node-name">${node.name}</div>
                <div class="node-version">${escapeHtml(node.version)}</div>
                <div class="node-health ${node.healthy ? "status-ok" : "status-error"}">
                    ${node.healthy ? "Healthy" : "Down"}
                </div>
            </div>
        `,
        )
        .join("");
}

async function generatePlan() {
    const desc = document.getElementById("deploymentDesc").value.trim();
    if (!desc) {
        alert("Please describe your deployment or command");
        return;
    }

    hideErrorBanner();
    clearLogs();
    renderTimeline("parse");

    try {
        const parseResp = await fetch("/api/nlp/parse", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: desc }),
        });
        if (!parseResp.ok) {
            const err = await parseResp.json();
            throw new Error(err.detail || "Parse failed");
        }

        const spec = await parseResp.json();
        currentSpec = spec;
        currentSpecType = spec.spec_type || "deployment";

        document.getElementById("specJson").textContent = JSON.stringify(spec, null, 2);
        renderTimeline("plan");

        if (currentSpecType === "deployment" && document.getElementById("simulateFailure").checked) {
            currentSpec.failure_injection_node = "node2";
        } else if (currentSpecType === "deployment") {
            delete currentSpec.failure_injection_node;
        }

        const previewResp = await fetch("/api/plan/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec_type: currentSpecType, spec: currentSpec }),
        });
        if (!previewResp.ok) {
            const err = await previewResp.json();
            throw new Error(err.detail || "Preview failed");
        }

        currentPreview = await previewResp.json();
        document.getElementById("commandOutput").textContent = currentPreview.exact_commands.join("\n");
        renderRiskChecks(currentPreview.risk_checks || []);

        const deployBtn = document.getElementById("deployBtn");
        deployBtn.textContent = currentSpecType === "command" ? "Execute Command" : "Deploy";
        deployBtn.disabled = false;

        const risky = Boolean(currentPreview.requires_confirmation || currentSpec.requires_confirmation);
        document.getElementById("confirmRiskWrap").classList.toggle("hidden", !risky);
        if (!risky) {
            document.getElementById("confirmRisk").checked = false;
        }

        addLog("Plan preview generated.", "info");
    } catch (error) {
        addLog(`Error generating plan: ${error.message}`, "error");
    }
}

function renderRiskChecks(checks) {
    const panel = document.getElementById("riskChecks");
    if (!checks.length) {
        panel.innerHTML = "<div class='risk-item'>No risk checks found.</div>";
        return;
    }
    panel.innerHTML = checks.map((c) => `<div class="risk-item">${escapeHtml(c)}</div>`).join("");
}

async function startDeploy() {
    if (!currentSpec || !currentSpecType) {
        alert("Generate a plan first");
        return;
    }
    if (isDeploying) {
        alert("Operation already in progress");
        return;
    }

    const confirmRisk = document.getElementById("confirmRisk").checked;
    if (currentSpecType === "command") {
        currentSpec.confirmed = confirmRisk;
        if (currentSpec.requires_confirmation && !confirmRisk) {
            alert("This command is risky. Please confirm before executing.");
            return;
        }
    }

    if (currentSpecType === "deployment" && document.getElementById("simulateFailure").checked) {
        currentSpec.failure_injection_node = "node2";
    }

    isDeploying = true;
    document.getElementById("deployBtn").disabled = true;
    clearLogs();

    try {
        const endpoint = currentSpecType === "command" ? "/api/command/execute" : "/api/deploy/spec";
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec: currentSpec }),
        });
        const data = await response.json();

        if (response.status === 409 && data.detail && data.detail.error === "NO_RUNNER") {
            showErrorBanner(data.detail.message || "No deployment runner available.");
            addLog(data.detail.message || "Runner unavailable.", "error");
            isDeploying = false;
            document.getElementById("deployBtn").disabled = false;
            return;
        }
        if (!response.ok) {
            throw new Error(data.detail || data.message || "Operation failed");
        }

        addLog(data.message || "Operation started.", "info");
        pollDeploymentStatus();
    } catch (error) {
        addLog(`Error starting operation: ${error.message}`, "error");
        isDeploying = false;
        document.getElementById("deployBtn").disabled = false;
    }
}

async function pollDeploymentStatus() {
    try {
        const response = await fetch("/api/deploy/status");
        const status = await response.json();

        if (status.current_stage) {
            renderTimeline(status.current_stage);
        }

        if (status.logs && status.logs.length) {
            const logsPanel = document.getElementById("logsPanel");
            logsPanel.innerHTML = status.logs
                .map((log) => `<p class="log-line">${escapeHtml(log)}</p>`)
                .join("");
            logsPanel.scrollTop = logsPanel.scrollHeight;
        }

        if (status.running) {
            setTimeout(pollDeploymentStatus, 1000);
            return;
        }

        isDeploying = false;
        document.getElementById("deployBtn").disabled = false;
        if (status.error) {
            addLog(`Failed: ${status.error}`, "error");
        } else {
            addLog("Completed.", "success");
            setTimeout(pollNodes, 1000);
        }
    } catch (error) {
        console.error("Error polling status:", error);
        if (isDeploying) {
            setTimeout(pollDeploymentStatus, 1000);
        }
    }
}

function addLog(message, type = "info") {
    const logsPanel = document.getElementById("logsPanel");
    const line = document.createElement("p");
    line.className = `log-line log-${type}`;
    line.textContent = message;
    logsPanel.appendChild(line);
    logsPanel.scrollTop = logsPanel.scrollHeight;
}

function clearLogs() {
    document.getElementById("logsPanel").innerHTML = "";
}

function showErrorBanner(message) {
    const banner = document.getElementById("errorBanner");
    document.getElementById("errorMessage").textContent = message;
    banner.style.display = "block";
}

function hideErrorBanner() {
    document.getElementById("errorBanner").style.display = "none";
}

function escapeHtml(text) {
    const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    };
    return String(text).replace(/[&<>"']/g, (m) => map[m]);
}

document.getElementById("generateBtn").addEventListener("click", generatePlan);
document.getElementById("deployBtn").addEventListener("click", startDeploy);
renderTimeline("parse");
pollNodes();
setInterval(pollNodes, 3000);
