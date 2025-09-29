import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import InteractiveMap from './components/InteractiveMap';
import AdminPanel from './components/AdminPanel';
import { AuthProvider, useAuth } from './components/auth/AuthProvider';
import LoginForm from './components/auth/LoginForm';
import './App.css';

const API_BASE = 'http://localhost:5000/api';

function AppContent() {
  const { user, loading, logout, checkAuthState } = useAuth();
  
  // Helper function to get authentication headers
  const getAuthHeaders = () => {
    if (user && user.tokens && user.tokens.idToken) {
      console.log('Auth headers available, user:', user.email);
      return {
        'Authorization': `Bearer ${user.tokens.idToken.toString()}`
      };
    }
    console.log('No auth headers available, user:', user ? 'exists but no tokens' : 'null');
    return {};
  };
  const [currentView, setCurrentView] = useState(() => {
    // Persist current view across page refreshes
    return localStorage.getItem('currentView') || 'home';
  });
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [rideData, setRideData] = useState(null);
  const [baselineData, setBaselineData] = useState(null);
  const [currentRideId, setCurrentRideId] = useState(null);
  const [selectedFault, setSelectedFault] = useState('RANDOM');
  const [branding, setBranding] = useState({
    app_title: 'AI Predictive Maintenance',
    app_subtitle: 'Theme Park Asset Management',
    company_name: 'Theme Park Operations'
  });
  const [systemStatus, setSystemStatus] = useState({ 
    simulator_ready: false, 
    lstm_trained: false, 
    total_rides: 0 
  });

  const faultTypes = [
    { value: 'RANDOM', label: 'Random (Realistic Distribution)' },
    { value: 'NORMAL', label: 'Normal Operation' },
    { value: 'OUTER_RACE_FAULT', label: 'Outer Race Fault' },
    { value: 'INNER_RACE_FAULT', label: 'Inner Race Fault' },
    { value: 'BALL_FAULT', label: 'Ball/Element Fault' },
    { value: 'CAGE_FAULT', label: 'Cage Fault' }
  ];

  useEffect(() => {
    if (user && user.tokens) {
      checkSystemStatus();
      loadBranding();
    }
  }, [user]);

  useEffect(() => {
    document.title = branding.app_title;
  }, [branding.app_title]);

  const loadBranding = async () => {
    try {
      const response = await axios.get('http://localhost:5001/api/admin/branding', {
        headers: getAuthHeaders()
      });
      if (response.data.success) {
        setBranding(response.data.branding);
      }
    } catch (error) {
      console.error('Failed to load branding:', error);
    }
  };

  const checkSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/status`, {
        headers: getAuthHeaders()
      });
      setSystemStatus(response.data);
    } catch (error) {
      console.error('Failed to check system status:', error);
    }
  };

  const trainModel = async () => {
    try {
      setIsSimulating(true);
      const response = await axios.post(`${API_BASE}/train-model`, {}, {
        headers: getAuthHeaders()
      });
      if (response.data.success) {
        await checkSystemStatus();
        alert('LSTM model trained successfully!');
      }
    } catch (error) {
      console.error('Training failed:', error);
      alert('Training failed: ' + error.message);
    } finally {
      setIsSimulating(false);
    }
  };

  const startSimulation = async () => {
    setIsSimulating(true);
    setRideData(null);
    setCurrentRideId(null);
    
    try {
      const payload = selectedFault === 'RANDOM' ? {} : { force_fault_type: selectedFault };
      
      // Add asset_id if an asset is selected
      if (selectedAsset && selectedAsset.id) {
        payload.asset_id = selectedAsset.id;
      }
      
      const response = await axios.post(`${API_BASE}/simulate-ride`, payload, {
        headers: getAuthHeaders()
      });
      
      if (response.data.success) {
        setRideData(response.data);
        setCurrentRideId(response.data.ride_id);
        setSystemStatus(prev => ({ ...prev, total_rides: prev.total_rides + 1 }));
      }
    } catch (error) {
      console.error('Simulation failed:', error);
      alert('Simulation failed: ' + error.message);
    } finally {
      setIsSimulating(false);
    }
  };

  const loadBaselineData = async () => {
    try {
      const response = await axios.get(`${API_BASE}/baseline-data`, {
        headers: getAuthHeaders()
      });
      if (response.data.success) {
        setBaselineData(response.data);
      }
    } catch (error) {
      console.error('Failed to load baseline:', error);
    }
  };

  useEffect(() => {
    if (user && user.tokens) {
      loadBaselineData();
    }
  }, [user]);

  const handleAssetClick = (asset) => {
    setSelectedAsset(asset);
    handleViewChange('simulation');
  };

  const formatChartData = (data) => {
    if (!data?.chart_data) return [];
    return data.chart_data.timestamps.map((time, index) => ({
      time: time.toFixed(1),
      magnitude: data.chart_data.magnitude[index]?.toFixed(2) || 0
    }));
  };

  const getChartHeight = (data) => {
    if (!data || data.length === 0) return 300;
    const values = data.map(d => parseFloat(d.magnitude || d.power || 0));
    const range = Math.max(...values) - Math.min(...values);
    return Math.max(300, Math.min(500, 300 + range * 20));
  };

  const getConfidenceColor = (confidence) => {
    if (confidence > 0.8) return '#10b981';
    if (confidence > 0.6) return '#f59e0b';
    return '#ef4444';
  };

  const getFaultSeverityColor = (severity) => {
    switch (severity) {
      case 'HIGH': return '#ef4444';
      case 'MEDIUM': return '#f59e0b';
      case 'LOW': return '#10b981';
      default: return '#6b7280';
    }
  };

  const handleViewChange = (view) => {
    setCurrentView(view);
    localStorage.setItem('currentView', view);
  };

  const renderNavigation = () => (
    <nav className="navigation">
      <button 
        className={currentView === 'home' ? 'active' : ''}
        onClick={() => handleViewChange('home')}
      >
        Home
      </button>
      <button 
        className={currentView === 'simulation' ? 'active' : ''}
        onClick={() => handleViewChange('simulation')}
      >
        Simulation
      </button>
      <button 
        className={currentView === 'admin' ? 'active' : ''}
        onClick={() => handleViewChange('admin')}
      >
        Admin
      </button>
      {user && (
        <div className="user-info">
          <span>Welcome, {user.email || user.username}</span>
          <button onClick={logout} className="logout-btn">Logout</button>
        </div>
      )}
    </nav>
  );

  // Show loading while checking auth state
  if (loading) {
    return (
      <div className="app">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Show login form if not authenticated
  if (!user) {
    return (
      <div className="app">
        <header className="header">
          <h1>{branding.app_title}</h1>
          <p>{branding.app_subtitle}</p>
        </header>
        <LoginForm onSuccess={checkAuthState} />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>{branding.app_title}</h1>
        <p>{selectedAsset ? `${selectedAsset.name} - ${selectedAsset.type}` : branding.app_subtitle}</p>
        {renderNavigation()}
      </header>

      {currentView === 'home' && (
        <div className="home-view">
          <div className="welcome-section">
            <h2>Welcome to {branding.app_title}</h2>
            <p>Click on any asset in the map below to run simulations and view AI analysis.</p>
          </div>
          <InteractiveMap onAssetClick={handleAssetClick} branding={branding} getAuthHeaders={getAuthHeaders} />
        </div>
      )}

      {currentView === 'admin' && <AdminPanel branding={branding} setBranding={setBranding} getAuthHeaders={getAuthHeaders} />}

      {currentView === 'simulation' && (
        <div className="simulation-view">
          <div className="status-bar">
            <div className={`status-indicator ${systemStatus.simulator_ready ? 'ready' : 'loading'}`}>
              {systemStatus.simulator_ready ? 'Simulator Ready' : 'Loading...'}
            </div>
            <div className={`status-indicator ${systemStatus.lstm_trained ? 'ready' : 'loading'}`}>
              {systemStatus.lstm_trained ? 'LSTM Trained' : 'LSTM Not Trained'}
            </div>
            <div className="ride-counter">
              Total Rides: {systemStatus.total_rides}
            </div>
          </div>

          <div className="control-panel">
            <div className="asset-info">
              {selectedAsset && (
                <div className="selected-asset">
                  <h3>Selected Asset: {selectedAsset.name}</h3>
                  <p>Type: {selectedAsset.type}</p>
                  <p>Status: {selectedAsset.status}</p>
                </div>
              )}
            </div>
            
            {!systemStatus.lstm_trained && (
              <button 
                className="train-btn"
                onClick={trainModel}
                disabled={isSimulating}
              >
                {isSimulating ? 'Training LSTM...' : 'Train LSTM Model'}
              </button>
            )}
            
            <div className="fault-selector">
              <label htmlFor="fault-select">Fault Type:</label>
              <select 
                id="fault-select"
                value={selectedFault} 
                onChange={(e) => setSelectedFault(e.target.value)}
                disabled={isSimulating}
              >
                {faultTypes.map(fault => (
                  <option key={fault.value} value={fault.value}>
                    {fault.label}
                  </option>
                ))}
              </select>
            </div>
            
            <button 
              className="simulate-btn"
              onClick={startSimulation}
              disabled={isSimulating || !systemStatus.simulator_ready || !selectedAsset}
            >
              {isSimulating ? 'Simulating...' : `Simulate ${selectedAsset?.name || 'Asset'}`}
            </button>
          </div>

          {isSimulating && (
            <div className="simulation-status">
              <div className="spinner"></div>
              <p>Running simulation for {selectedAsset?.name || 'selected asset'}...</p>
            </div>
          )}

          {rideData && (
            <div className="results">
              <div className="ride-info">
                <h2>Ride #{rideData.ride_id} Complete</h2>
                <div className="info-grid">
                  <div className="info-card">
                    <h3>Duration</h3>
                    <p>{rideData.duration}s</p>
                  </div>
                  <div className="info-card">
                    <h3>Max G-Force</h3>
                    <p>{rideData.max_gforce.toFixed(2)}g</p>
                  </div>
                  <div className="info-card">
                    <h3>RMS Vibration</h3>
                    <p>{rideData.rms_acceleration.toFixed(3)}</p>
                  </div>
                </div>
              </div>

              <div className="ai-analysis">
                <h2>LSTM Fault Analysis</h2>
                
                {systemStatus.lstm_trained ? (
                  <div className="analysis-card">
                    <div className="fault-prediction">
                      <div className="predicted-fault">
                        <h3>AI Prediction</h3>
                        <div 
                          className="fault-badge" 
                          style={{ 
                            backgroundColor: rideData.is_predicted_healthy ? '#10b981' : '#ef4444',
                            color: 'white',
                            padding: '12px 24px',
                            borderRadius: '8px',
                            fontWeight: 'bold',
                            textAlign: 'center',
                            marginBottom: '15px'
                          }}
                        >
                          {rideData.predicted_fault_type.replace(/_/g, ' ')}
                        </div>
                        <div className="metrics">
                          <p><strong>Confidence:</strong> 
                            <span style={{ color: getConfidenceColor(rideData.prediction_confidence) }}>
                              {(rideData.prediction_confidence * 100).toFixed(1)}%
                            </span>
                          </p>
                          <p><strong>Severity:</strong> 
                            <span style={{ color: getFaultSeverityColor(rideData.fault_severity) }}>
                              {rideData.fault_severity}
                            </span>
                          </p>
                        </div>
                      </div>
                      
                      <div className="actual-vs-predicted">
                        <h3>Validation (Ride #{currentRideId})</h3>
                        <p><strong>Actual Condition:</strong> {rideData.actual_fault_type.replace(/_/g, ' ')}</p>
                        <p><strong>Prediction:</strong> 
                          {rideData.prediction_correct ? 
                            <span style={{color: '#10b981'}}> CORRECT</span> : 
                            <span style={{color: '#ef4444'}}> INCORRECT</span>
                          }
                        </p>
                        <p><strong>Health Status:</strong> 
                          {rideData.is_actually_faulty ? 
                            <span style={{color: '#ef4444'}}> FAULTY</span> : 
                            <span style={{color: '#10b981'}}> HEALTHY</span>
                          }
                        </p>
                      </div>
                    </div>
                    
                    {rideData.fault_probabilities && (
                      <div className="fault-probabilities">
                        <h3>Detailed Fault Probabilities</h3>
                        <div className="prob-bars">
                          {Object.entries(rideData.fault_probabilities).map(([fault, prob]) => (
                            <div key={fault} className="prob-bar">
                              <span className="fault-name">{fault.replace(/_/g, ' ')}</span>
                              <div className="bar-container">
                                <div 
                                  className="bar-fill" 
                                  style={{ 
                                    width: `${prob * 100}%`,
                                    backgroundColor: prob > 0.5 ? '#ef4444' : prob > 0.2 ? '#f59e0b' : '#10b981'
                                  }}
                                ></div>
                                <span className="prob-value">{(prob * 100).toFixed(1)}%</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="model-not-trained">
                    <p>LSTM model not trained. Click "Train LSTM Model" to enable fault analysis.</p>
                  </div>
                )}
              </div>

              <div className="chart-section">
                <h2>Vibration Analysis</h2>
                
                <div className="chart-container">
                  <h3>Time Domain - Acceleration Magnitude (m/s²)</h3>
                  <ResponsiveContainer width="100%" height={getChartHeight(formatChartData(rideData))}>
                    <LineChart data={formatChartData(rideData)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -5 }} />
                      <YAxis label={{ value: 'Acceleration (m/s²)', angle: -90, position: 'insideLeft' }} />
                      <Tooltip formatter={(value, name) => [`${value} m/s²`, name]} />
                      
                      {baselineData && (
                        <Line 
                          data={formatChartData(baselineData)}
                          type="monotone" 
                          dataKey="magnitude" 
                          stroke="#10b981" 
                          strokeWidth={1}
                          dot={false}
                          name="Baseline (Normal)"
                          strokeDasharray="5 5"
                        />
                      )}
                      
                      <Line 
                        type="monotone" 
                        dataKey="magnitude" 
                        stroke={rideData.is_actually_faulty ? "#ef4444" : "#2563eb"} 
                        strokeWidth={2}
                        dot={false}
                        name={`Current Ride (${rideData.actual_fault_type.replace(/_/g, ' ')})`}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                <div className="chart-container">
                  <h3>Frequency Domain - Power Spectral Density</h3>
                  {rideData.frequency_data && rideData.frequency_data.length > 0 ? (
                    <ResponsiveContainer width="100%" height={getChartHeight(rideData.frequency_data)}>
                      <LineChart data={rideData.frequency_data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis 
                          dataKey="frequency" 
                          type="number"
                          scale="linear"
                          domain={[0, 25]}
                          label={{ value: 'Frequency (Hz)', position: 'insideBottom', offset: -5 }} 
                        />
                        <YAxis label={{ value: 'Power (dB)', angle: -90, position: 'insideLeft' }} />
                        <Tooltip formatter={(value, name) => [`${Number(value).toFixed(1)} dB`, name]} />
                        
                        {baselineData && baselineData.frequency_data && (
                          <Line 
                            data={baselineData.frequency_data}
                            type="monotone" 
                            dataKey="power" 
                            stroke="#10b981" 
                            strokeWidth={1}
                            dot={false}
                            name="Original Ride Data (Baseline)"
                            strokeDasharray="5 5"
                          />
                        )}
                        
                        <Line 
                          type="monotone" 
                          dataKey="power" 
                          stroke={rideData.is_actually_faulty ? "#ef4444" : "#2563eb"} 
                          strokeWidth={2}
                          dot={false}
                          name={`Current Ride (${rideData.actual_fault_type.replace(/_/g, ' ')})`}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8f9fa' }}>
                      <p>No frequency data available</p>
                    </div>
                  )}
                  
                  {rideData.fault_frequencies && rideData.fault_frequencies.length > 0 && (
                    <div className="fault-frequencies">
                      <p><strong>Fault Frequencies Detected:</strong> {rideData.fault_frequencies.map(f => f.toFixed(1)).join(', ')} Hz</p>
                    </div>
                  )}
                </div>

                {rideData.is_actually_faulty && (
                  <div className="fault-summary">
                    <h3>Fault Analysis Summary</h3>
                    <div className="fault-details">
                      <p><strong>Fault Type:</strong> {rideData.actual_fault_type.replace(/_/g, ' ')}</p>
                      <p><strong>Characteristic Frequencies:</strong> {rideData.fault_frequencies && rideData.fault_frequencies.length > 0 ? rideData.fault_frequencies.map(f => f.toFixed(1)).join(', ') + ' Hz' : 'None detected'}</p>
                      <p><strong>Severity:</strong> {rideData.fault_severity}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;