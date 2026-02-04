let currentSpec = {};
let currentSpecType = null;
let isDeploying = false;

async function pollNodes() {
    try {
        const response = await fetch('/api/nodes');
        const nodes = await response.json();
        renderNodes(nodes);
    } catch (error) {
        console.error('Error polling nodes:', error);
    }
}

function renderNodes(nodes) {
    const panel = document.getElementById('nodesPanel');
    
    if (!nodes || nodes.length === 0) {
        panel.innerHTML = '<div class="loading">No nodes available</div>';
        return;
    }
    
    const html = nodes.map(node => `
        <div class="node-card ${node.healthy ? 'healthy' : 'unhealthy'}">
            <div class="node-name">${node.name}</div>
            <div class="node-version">v${node.version.replace('v', '')}</div>
            <div class="node-health ${node.healthy ? 'status-ok' : 'status-error'}">
                ${node.healthy ? '✓ Healthy' : '✗ Down'}
            </div>
        </div>
    `).join('');
    
    panel.innerHTML = html;
}

async function generatePlan() {
    const desc = document.getElementById('deploymentDesc').value;
    
    if (!desc.trim()) {
        alert('Please describe your deployment or command');
        return;
    }
    
    try {
        const parseResp = await fetch('/api/nlp/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: desc })
        });
        
        const spec = await parseResp.json();
        currentSpec = spec;
        currentSpecType = spec.spec_type || 'deployment';
        
        // Display the parsed spec
        document.getElementById('specJson').textContent = JSON.stringify(spec, null, 2);
        
        // If it's a deployment, generate artifacts
        if (currentSpecType === 'deployment') {
            const genResp = await fetch(`/api/generate?spec=${encodeURIComponent(JSON.stringify(spec))}`);
            const plan = await genResp.json();
            
            const snippets = plan.snippets || [];
            document.getElementById('commandOutput').textContent = snippets.join('\n');
        } else if (currentSpecType === 'command') {
            // For commands, show what will be executed
            document.getElementById('commandOutput').textContent = 
                `Will execute: ${spec.command_type}\n` +
                `Target nodes: ${spec.target_nodes.join(', ')}`;
        }
        
        // Update button text based on spec type
        const deployBtn = document.getElementById('deployBtn');
        if (currentSpecType === 'command') {
            deployBtn.textContent = `Execute ${spec.command_type.charAt(0).toUpperCase() + spec.command_type.slice(1)}`;
        } else {
            deployBtn.textContent = 'Deploy';
        }
        
        deployBtn.disabled = false;
        
        addLog('Plan generated successfully', 'info');
    } catch (error) {
        addLog(`Error generating plan: ${error.message}`, 'error');
        alert('Error generating plan');
    }
}

async function startDeploy() {
    if (!currentSpec) {
        alert('Generate a plan first');
        return;
    }
    
    if (currentSpecType === 'deployment' && !currentSpec.target_version) {
        alert('Generate a plan first');
        return;
    }
    
    if (currentSpecType === 'command' && !currentSpec.command_type) {
        alert('Generate a plan first');
        return;
    }
    
    if (isDeploying) {
        alert('Operation already in progress');
        return;
    }
    
    isDeploying = true;
    document.getElementById('deployBtn').disabled = true;
    clearLogs();
    hideErrorBanner();
    
    try {
        let response;
        let apiEndpoint;
        let bodyData;
        
        if (currentSpecType === 'deployment') {
            apiEndpoint = '/api/deploy/spec';
            bodyData = { spec: currentSpec };
        } else if (currentSpecType === 'command') {
            apiEndpoint = '/api/command/execute';
            bodyData = { spec: currentSpec };
        } else {
            throw new Error('Unknown spec type');
        }
        
        response = await fetch(apiEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });
        
        const data = await response.json();
        
        if (response.status === 409 && data.error === 'NO_RUNNER') {
            showErrorBanner('No deployment runner available. Please ensure nodes are running.');
            addLog('ERROR: No healthy nodes available', 'error');
            isDeploying = false;
            document.getElementById('deployBtn').disabled = false;
            return;
        }
        
        if (!response.ok) {
            addLog(`Error: ${data.message || 'Operation failed'}`, 'error');
            isDeploying = false;
            document.getElementById('deployBtn').disabled = false;
            return;
        }
        
        addLog(`${currentSpecType === 'command' ? 'Command' : 'Deployment'} started`, 'info');
        
        pollDeploymentStatus();
        
    } catch (error) {
        addLog(`Error starting operation: ${error.message}`, 'error');
        isDeploying = false;
        document.getElementById('deployBtn').disabled = false;
    }
}

async function pollDeploymentStatus() {
    try {
        const response = await fetch('/api/deploy/status');
        const status = await response.json();
        
        if (status.logs && status.logs.length > 0) {
            const logsPanel = document.getElementById('logsPanel');
            logsPanel.innerHTML = status.logs
                .map(log => `<p class="log-line">${escapeHtml(log)}</p>`)
                .join('');
            
            logsPanel.scrollTop = logsPanel.scrollHeight;
        }
        
        if (status.running) {
            setTimeout(pollDeploymentStatus, 1000);
        } else {
            isDeploying = false;
            
            if (status.error) {
                addLog(`Deployment failed: ${status.error}`, 'error');
                if (status.error === 'NO_RUNNER') {
                    showErrorBanner('No deployment runner available.');
                }
            } else {
                addLog('Deployment completed successfully', 'success');
                
                setTimeout(pollNodes, 1000);
            }
            
            document.getElementById('deployBtn').disabled = false;
        }
    } catch (error) {
        console.error('Error polling status:', error);
        if (isDeploying) {
            setTimeout(pollDeploymentStatus, 1000);
        }
    }
}

function addLog(message, type = 'info') {
    const logsPanel = document.getElementById('logsPanel');
    const logLine = document.createElement('p');
    logLine.className = `log-line log-${type}`;
    logLine.textContent = message;
    logsPanel.appendChild(logLine);
    logsPanel.scrollTop = logsPanel.scrollHeight;
}

function clearLogs() {
    document.getElementById('logsPanel').innerHTML = '';
}

function showErrorBanner(message) {
    const banner = document.getElementById('errorBanner');
    document.getElementById('errorMessage').textContent = message;
    banner.style.display = 'block';
}

function hideErrorBanner() {
    document.getElementById('errorBanner').style.display = 'none';
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

document.getElementById('generateBtn').addEventListener('click', generatePlan);
document.getElementById('deployBtn').addEventListener('click', startDeploy);

pollNodes();
setInterval(pollNodes, 3000);
