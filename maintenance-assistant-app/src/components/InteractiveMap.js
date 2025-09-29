import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const InteractiveMap = ({ onAssetClick, branding, getAuthHeaders }) => {
  const [mapConfig, setMapConfig] = useState(null);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [hoveredAlert, setHoveredAlert] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const mapRef = useRef(null);

  useEffect(() => {
    loadMapConfig();
    loadAlerts();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      loadMapConfig();
      loadAlerts();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadMapConfig = async () => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      const response = await axios.get('http://localhost:5001/api/map/config', authHeaders);
      if (response.data.success) {
        setMapConfig(response.data);
        // Update parent branding if provided
        if (response.data.branding && branding) {
          Object.assign(branding, response.data.branding);
        }
      }
    } catch (error) {
      console.error('Failed to load map config:', error);
    }
  };

  const loadAlerts = async () => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      const response = await axios.get('http://localhost:5001/api/alerts', authHeaders);
      if (response.data.success) {
        setAlerts(response.data.alerts);
      }
    } catch (error) {
      // Silently fail if alerts endpoint doesn't exist yet or authentication fails
      console.log('Alerts endpoint not available or authentication required');
    }
  };

  const handleAssetClick = (asset) => {
    setSelectedAsset(asset);
    if (onAssetClick) {
      onAssetClick(asset);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#10b981';
      case 'maintenance': return '#f59e0b';
      case 'offline': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getAlertIcon = (severity) => {
    return '!';  // Exclamation mark - will be styled with yellow triangle background
  };

  const getAlertColor = (severity) => {
    switch (severity) {
      case 'critical': return '#dc2626';
      case 'high': return '#ea580c';
      case 'medium': return '#d97706';
      case 'low': return '#059669';
      default: return '#6b7280';
    }
  };

  const handleAlertHover = (alert, event) => {
    setHoveredAlert(alert);
    setTooltipPosition({ x: event.clientX, y: event.clientY });
  };

  const handleAlertLeave = () => {
    setHoveredAlert(null);
  };

  const handleAlertClick = async (alert) => {
    const asset = mapConfig.assets.find(a => a.id === alert.asset_id);
    if (!asset) return;
    
    // Get user token from auth context
    try {
      const { fetchAuthSession } = await import('aws-amplify/auth');
      const session = await fetchAuthSession();
      const userToken = session.tokens?.idToken?.toString();
      
      if (!userToken) {
        alert('Please log in to access the chat interface');
        return;
      }
      
      // Open chat interface in new window with alert context and user token
      const chatUrl = `http://localhost:5002/?asset=${encodeURIComponent(asset.name)}&fault=${encodeURIComponent(alert.fault_type)}&severity=${encodeURIComponent(alert.severity)}&alert=${alert.id}&token=${encodeURIComponent(userToken)}`;
      
      const chatWindow = window.open(
        chatUrl,
        'maintainx-chat',
        'width=900,height=700,scrollbars=yes,resizable=yes,status=yes,location=yes,toolbar=no,menubar=no'
      );
      
      if (chatWindow) {
        chatWindow.focus();
      } else {
        // Fallback if popup blocked
        window.location.href = chatUrl;
      }
    } catch (error) {
      console.error('Failed to get user token:', error);
      alert('Authentication error. Please refresh and try again.');
    }
  };

  const formatAlertTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };

  if (!mapConfig) {
    return <div className="map-loading">Loading map...</div>;
  }

  if (!mapConfig.map) {
    return (
      <div className="no-map-message">
        <h3>No Map Configured</h3>
        <p>Please configure a facility map in the admin panel to view assets.</p>
        <p>Or run database initialization: <code>python3 init_db.py</code></p>
      </div>
    );
  }

  return (
    <div className="interactive-map">
      <div className="map-container" ref={mapRef}>
        <img 
          src={mapConfig.map.image_path} 
          alt="Theme Park Map"
          className="park-map"
          style={{ 
            width: '100%', 
            height: 'auto',
            maxWidth: `${mapConfig.map.width}px`
          }}
        />
        
        {mapConfig.assets.map(asset => (
          <div
            key={asset.id}
            className={`asset-marker ${selectedAsset?.id === asset.id ? 'selected' : ''}`}
            style={{
              position: 'absolute',
              left: `${(asset.x / mapConfig.map.width) * 100}%`,
              top: `${(asset.y / mapConfig.map.height) * 100}%`,
              width: `${(asset.width / mapConfig.map.width) * 100}%`,
              height: `${(asset.height / mapConfig.map.height) * 100}%`,
              backgroundColor: getStatusColor(asset.status),
              border: '2px solid white',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontWeight: 'bold',
              color: 'white',
              textShadow: '1px 1px 2px rgba(0,0,0,0.7)',
              transform: 'translate(-50%, -50%)',
              minWidth: '60px',
              minHeight: '30px',
              opacity: 0.9,
              transition: 'all 0.3s ease'
            }}
            onClick={() => handleAssetClick(asset)}
            title={`${asset.name} (${asset.type}) - ${asset.status}`}
          >
            {asset.name}
          </div>
        ))}
        
        {/* Alert Icons */}
        {alerts.map(alert => {
          const asset = mapConfig.assets.find(a => a.id === alert.asset_id);
          if (!asset) return null;
          
          return (
            <div
              key={`alert-${alert.id}`}
              className="alert-icon"
              style={{
                position: 'absolute',
                left: `${(asset.x / mapConfig.map.width) * 100}%`,
                top: `${(asset.y / mapConfig.map.height) * 100}%`,
                transform: 'translate(-50%, -150%)',
                width: `${Math.max(32, (40 / mapConfig.map.width) * 100)}px`,
                height: `${Math.max(32, (40 / mapConfig.map.width) * 100)}px`,
                backgroundColor: alert.severity === 'critical' ? '#dc2626' : '#fbbf24',  // Red for critical, yellow for others
                clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)',  // Triangle shape
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: `${Math.max(16, (20 / mapConfig.map.width) * 100)}px`,
                color: 'white',   // White exclamation mark
                fontWeight: 'bold',
                cursor: 'pointer',
                zIndex: 1000,
                opacity: 1,       // Full opacity for maximum visibility
                animation: alert.severity === 'critical' ? 'pulse 0.8s infinite, bounce 2s infinite' : 
                          alert.severity === 'high' ? 'pulse 1.2s infinite' : 
                          'glow 2s ease-in-out infinite alternate',
                filter: 'drop-shadow(3px 3px 8px rgba(0,0,0,0.7))',
                border: '2px solid rgba(255,255,255,0.8)',
                boxShadow: '0 0 15px rgba(251, 191, 36, 0.8)'
              }}
              onMouseEnter={(e) => handleAlertHover(alert, e)}
              onMouseLeave={handleAlertLeave}
              onMouseMove={(e) => setTooltipPosition({ x: e.clientX, y: e.clientY })}
              onClick={() => handleAlertClick(alert)}
            >
              {getAlertIcon(alert.severity)}
            </div>
          );
        })}
      </div>
      
      {/* Alert Tooltip */}
      {hoveredAlert && (
        <div 
          className="alert-tooltip"
          style={{
            position: 'fixed',
            left: tooltipPosition.x + 10,
            top: tooltipPosition.y - 10,
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            color: 'white',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            zIndex: 10000,
            pointerEvents: 'none',
            maxWidth: '200px',
            border: `2px solid ${getAlertColor(hoveredAlert.severity)}`
          }}
        >
          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
            <span style={{ 
              display: 'inline-block',
              width: '18px',
              height: '18px',
              backgroundColor: hoveredAlert.severity === 'critical' ? '#dc2626' : '#fbbf24',
              clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)',
              position: 'relative',
              marginRight: '8px',
              verticalAlign: 'middle',
              border: '1px solid rgba(255,255,255,0.8)',
              boxShadow: '0 0 8px rgba(251, 191, 36, 0.6)'
            }}>
              <span style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                color: 'white',
                fontSize: '11px',
                fontWeight: 'bold'
              }}>
                {getAlertIcon(hoveredAlert.severity)}
              </span>
            </span>
            <span style={{ 
              color: hoveredAlert.severity === 'critical' ? '#dc2626' : '#fbbf24',
              fontWeight: 'bold'
            }}>
              {hoveredAlert.severity.toUpperCase()}
            </span>
          </div>
          <div><strong>Fault:</strong> {hoveredAlert.fault_type}</div>
          <div><strong>Time:</strong> {formatAlertTime(hoveredAlert.timestamp)}</div>
          {hoveredAlert.confidence && (
            <div><strong>Confidence:</strong> {(hoveredAlert.confidence * 100).toFixed(0)}%</div>
          )}
          <div style={{ marginTop: '8px', fontSize: '11px', fontStyle: 'italic', opacity: 0.8 }}>
            Click to chat with AI assistant
          </div>
        </div>
      )}
      
      {selectedAsset && (
        <div className="asset-info">
          <h3>{selectedAsset.name}</h3>
          <p><strong>Type:</strong> {selectedAsset.type}</p>
          <p><strong>Status:</strong> 
            <span style={{ color: getStatusColor(selectedAsset.status) }}>
              {selectedAsset.status.toUpperCase()}
            </span>
          </p>
          <button 
            className="simulate-btn"
            onClick={() => onAssetClick && onAssetClick(selectedAsset)}
          >
            Run Simulation
          </button>
        </div>
      )}
      
      <style jsx>{`
        @keyframes pulse {
          0% { transform: translate(-50%, -150%) scale(1); }
          50% { transform: translate(-50%, -150%) scale(1.2); }
          100% { transform: translate(-50%, -150%) scale(1); }
        }
        
        @keyframes bounce {
          0%, 20%, 50%, 80%, 100% { transform: translate(-50%, -150%) translateY(0); }
          40% { transform: translate(-50%, -150%) translateY(-8px); }
          60% { transform: translate(-50%, -150%) translateY(-4px); }
        }
        
        @keyframes glow {
          0% { 
            box-shadow: 0 0 15px rgba(251, 191, 36, 0.8);
            filter: drop-shadow(3px 3px 8px rgba(0,0,0,0.7)) brightness(1);
          }
          100% { 
            box-shadow: 0 0 25px rgba(251, 191, 36, 1), 0 0 35px rgba(251, 191, 36, 0.6);
            filter: drop-shadow(3px 3px 8px rgba(0,0,0,0.7)) brightness(1.2);
          }
        }
      `}</style>
    </div>
  );
};

export default InteractiveMap;