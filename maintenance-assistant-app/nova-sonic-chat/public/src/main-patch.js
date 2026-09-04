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

    // Build DOM safely: URL-derived values are set via textContent so they are
    // rendered as text, never parsed as HTML (prevents DOM-based XSS).
    const ALLOWED_SEVERITIES = ['low', 'medium', 'high', 'unknown'];
    const safeSeverityClass = ALLOWED_SEVERITIES.includes(faultContext.severity)
        ? faultContext.severity
        : 'unknown';

    const heading = document.createElement('h3');
    heading.textContent = 'Alert Context';
    contextDiv.appendChild(heading);

    const makeRow = (label, value) => {
        const p = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = label;
        p.appendChild(strong);
        p.appendChild(document.createTextNode(' ' + value));
        return p;
    };

    contextDiv.appendChild(makeRow('Asset:', faultContext.asset));
    contextDiv.appendChild(makeRow('Fault Type:', faultContext.fault));

    const severityRow = document.createElement('p');
    const severityStrong = document.createElement('strong');
    severityStrong.textContent = 'Severity:';
    severityRow.appendChild(severityStrong);
    severityRow.appendChild(document.createTextNode(' '));
    const severityValue = document.createElement('span');
    severityValue.className = `severity-${safeSeverityClass}`;
    severityValue.textContent = String(faultContext.severity).toUpperCase();
    severityRow.appendChild(severityValue);
    contextDiv.appendChild(severityRow);

    document.getElementById('app').insertBefore(contextDiv, document.getElementById('status'));
}

// Call this when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    displayFaultContext();
});
