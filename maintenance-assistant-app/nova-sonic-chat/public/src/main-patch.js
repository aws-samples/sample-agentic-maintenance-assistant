// Extract fault context from URL parameters
function getFaultContextFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    return {
        asset: urlParams.get('asset') || 'Unknown Asset',
        fault: urlParams.get('fault') || 'Unknown Fault',
        severity: urlParams.get('severity') || 'unknown',
        alert: urlParams.get('alert') || '',
        token: urlParams.get('token') || ''
    };
}

const faultContext = getFaultContextFromURL();

// Update system prompt to include maintenance context
let SYSTEM_PROMPT = `You are an AI maintenance assistant helping with equipment diagnostics and repair. 
You have access to maintenance knowledge and can provide guidance on troubleshooting and fixing issues.
Keep your responses concise and actionable, typically 2-3 sentences for quick exchanges.
Focus on practical solutions and safety considerations.`;

// Display fault context in the UI
function displayFaultContext() {
    const contextDiv = document.createElement('div');
    contextDiv.className = 'fault-context';
    contextDiv.innerHTML = `
        <h3>Alert Context</h3>
        <p><strong>Asset:</strong> ${faultContext.asset}</p>
        <p><strong>Fault Type:</strong> ${faultContext.fault}</p>
        <p><strong>Severity:</strong> <span class="severity-${faultContext.severity}">${faultContext.severity.toUpperCase()}</span></p>
    `;
    document.getElementById('app').insertBefore(contextDiv, document.getElementById('status'));
}

// Call this when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    displayFaultContext();
});
