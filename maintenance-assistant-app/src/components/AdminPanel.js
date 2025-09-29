import React, { useState, useEffect } from 'react';
import axios from 'axios';

const AdminPanel = ({ branding, setBranding, getAuthHeaders }) => {
  const [activeTab, setActiveTab] = useState(() => {
    // Persist active tab across page refreshes
    return localStorage.getItem('adminActiveTab') || 'maps';
  });
  const [maps, setMaps] = useState([]);
  const [assetTypes, setAssetTypes] = useState([]);
  const [simulators, setSimulators] = useState([]);
  const [assets, setAssets] = useState([]);

  const [isMarking, setIsMarking] = useState(false);
  const [newAsset, setNewAsset] = useState({});
  const [brandingForm, setBrandingForm] = useState(branding || {
    app_title: 'AI Predictive Maintenance',
    app_subtitle: 'Theme Park Asset Management',
    company_name: 'Theme Park Operations'
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (activeTab === 'maps') {
      loadData();
    }
  }, [activeTab]);

  const loadData = async () => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      const [mapsRes, typesRes, simulatorsRes, assetsRes] = await Promise.all([
        axios.get('http://localhost:5001/api/admin/maps', authHeaders),
        axios.get('http://localhost:5001/api/admin/asset-types', authHeaders),
        axios.get('http://localhost:5001/api/admin/simulators', authHeaders),
        axios.get('http://localhost:5001/api/admin/assets', authHeaders)
      ]);

      // Mark active map
      const mapsWithActive = (mapsRes.data.maps || []).map(map => ({
        ...map,
        active: map.path === mapsRes.data.active_map
      }));

      setMaps(mapsWithActive);
      setAssetTypes(typesRes.data.asset_types || []);
      setSimulators(simulatorsRes.data.simulators || []);
      setAssets(assetsRes.data.assets || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const setActiveMap = async (imagePath) => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.post('http://localhost:5001/api/admin/maps/active', {
        image_path: imagePath,
        name: 'Theme Park Map'
      }, authHeaders);
      alert('Map updated successfully!');
      loadData(); // Refresh data to update UI
    } catch (error) {
      console.error('Failed to set active map:', error);
    }
  };

  const createSimulator = async (data) => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.post('http://localhost:5001/api/admin/simulators', data, authHeaders);
      setNewAsset({});
      loadData();
      alert('Simulator created successfully!');
    } catch (error) {
      console.error('Failed to create simulator:', error);
    }
  };

  const createAssetType = async (data) => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.post('http://localhost:5001/api/admin/asset-types', data, authHeaders);
      setNewAsset({});
      loadData();
      alert('Asset type created successfully!');
    } catch (error) {
      console.error('Failed to create asset type:', error);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const authHeaders = getAuthHeaders ? getAuthHeaders() : {};
      const response = await axios.post('http://localhost:5001/api/admin/maps/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...authHeaders
        }
      });

      if (response.data.success) {
        alert('Map uploaded successfully!');
        loadData();
      }
    } catch (error) {
      console.error('Failed to upload map:', error);
      alert('Failed to upload map');
    }
  };

  const handleAssetModelUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const authHeaders = getAuthHeaders ? getAuthHeaders() : {};
      const response = await axios.post('http://localhost:5001/api/admin/models/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...authHeaders
        }
      });

      if (response.data.success) {
        setNewAsset({ ...newAsset, model_path: response.data.path });
        alert('Model file uploaded for asset!');
      }
    } catch (error) {
      console.error('Failed to upload model file:', error);
      alert('Failed to upload model file');
    }
  };

  const handleMapClick = (event) => {
    if (!isMarking) return;

    const rect = event.target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Scale coordinates to match homepage display (1200x800)
    const scaleX = 1200 / rect.width;
    const scaleY = 800 / rect.height;

    setNewAsset({
      ...newAsset,
      map_x: x * scaleX,
      map_y: y * scaleY
    });
    setIsMarking(false);
  };

  const deleteItem = async (type, id) => {
    if (!window.confirm('Are you sure you want to delete this item?')) return;

    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.delete(`http://localhost:5001/api/admin/${type}/${id}`, authHeaders);
      loadData();
      alert('Item deleted successfully!');
    } catch (error) {
      console.error('Failed to delete item:', error);
      alert('Failed to delete item');
    }
  };

  const deleteMap = async (filename) => {
    if (!window.confirm('Are you sure you want to delete this map?')) return;

    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.delete(`http://localhost:5001/api/admin/maps/${filename}`, authHeaders);
      loadData();
      alert('Map deleted successfully!');
    } catch (error) {
      console.error('Failed to delete map:', error);
      alert('Failed to delete map');
    }
  };

  const createAsset = async () => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.post('http://localhost:5001/api/admin/assets', newAsset, authHeaders);
      setNewAsset({});
      loadData();
      alert('Asset created successfully!');
    } catch (error) {
      console.error('Failed to create asset:', error);
    }
  };

  const saveBranding = async () => {
    try {
      const authHeaders = getAuthHeaders ? { headers: getAuthHeaders() } : {};
      await axios.post('http://localhost:5001/api/admin/branding', {
        branding: brandingForm
      }, authHeaders);
      setBranding(brandingForm);
      alert('Branding updated successfully!');
    } catch (error) {
      console.error('Failed to save branding:', error);
      alert('Failed to save branding');
    }
  };

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h1>Admin Panel</h1>
        <div className="admin-tabs">
          {['branding', 'maps', 'simulators', 'asset-types', 'assets'].map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => {
                setActiveTab(tab);
                localStorage.setItem('adminActiveTab', tab);
              }}
            >
              {tab.replace('-', ' ').toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'branding' && (
        <div className="tab-content">
          <h2>Branding Configuration</h2>
          <div className="form-section">
            <div className="form-group">
              <label>Application Title:</label>
              <input
                type="text"
                value={brandingForm.app_title}
                onChange={(e) => setBrandingForm({ ...brandingForm, app_title: e.target.value })}
                placeholder="AI Predictive Maintenance"
              />
            </div>
            <div className="form-group">
              <label>Application Subtitle:</label>
              <input
                type="text"
                value={brandingForm.app_subtitle}
                onChange={(e) => setBrandingForm({ ...brandingForm, app_subtitle: e.target.value })}
                placeholder="Theme Park Asset Management"
              />
            </div>
            <div className="form-group">
              <label>Company Name:</label>
              <input
                type="text"
                value={brandingForm.company_name}
                onChange={(e) => setBrandingForm({ ...brandingForm, company_name: e.target.value })}
                placeholder="Theme Park Operations"
              />
            </div>
            <button onClick={saveBranding} className="save-btn">Save Branding</button>
          </div>
        </div>
      )}

      {activeTab === 'maps' && (
        <div className="tab-content">
          <h2>Map Management</h2>

          <div className="upload-section">
            <h3>Upload New Map</h3>
            <input
              type="file"
              accept=".png,.jpg,.jpeg"
              onChange={handleFileUpload}
              className="file-input"
            />
            <p className="upload-hint">Supported formats: PNG, JPG, JPEG</p>
          </div>

          <div className="maps-grid">
            {maps.map(map => {
              const isActive = map.active;
              return (
                <div key={map.filename} className={`map-card ${isActive ? 'active-map' : ''}`}>
                  <img src={map.path} alt={map.name} style={{ width: '200px', height: '150px', objectFit: 'cover' }} />
                  <h3>{map.name}</h3>
                  <div className="map-buttons">
                    {isActive ? (
                      <button className="active-btn" disabled>Active</button>
                    ) : (
                      <button onClick={() => setActiveMap(map.path)}>Set Active</button>
                    )}
                  </div>
                  <div className="map-actions">
                    <button className="delete-btn" onClick={() => deleteMap(map.filename)}>Delete</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === 'simulators' && (
        <div className="tab-content">
          <h2>Simulators</h2>
          <div className="form-section">
            <input placeholder="Simulator Name" value={newAsset.name || ''} onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })} />
            <input placeholder="Class Name (e.g. RideSimulator)" value={newAsset.class_name || ''} onChange={(e) => setNewAsset({ ...newAsset, class_name: e.target.value })} />
            <input placeholder="Description" value={newAsset.description || ''} onChange={(e) => setNewAsset({ ...newAsset, description: e.target.value })} />
            <button onClick={() => createSimulator(newAsset)}>Create Simulator</button>
          </div>
          <div className="items-list">
            {simulators.map(sim => (
              <div key={sim.id} className="item-card">
                <h3>{sim.name}</h3>
                <p>{sim.description}</p>
                <small>Class: {sim.class_name}</small>
                <button className="delete-btn" onClick={() => deleteItem('simulators', sim.id)}>Delete</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'asset-types' && (
        <div className="tab-content">
          <h2>Asset Types</h2>
          <div className="form-section">
            <input placeholder="Name" value={newAsset.name || ''} onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })} />
            <input placeholder="Description" value={newAsset.description || ''} onChange={(e) => setNewAsset({ ...newAsset, description: e.target.value })} />
            <select value={newAsset.simulator_id || ''} onChange={(e) => setNewAsset({ ...newAsset, simulator_id: e.target.value })}>
              <option value="">Select Simulator</option>
              {simulators.map(sim => (
                <option key={sim.id} value={sim.id}>{sim.name}</option>
              ))}
            </select>
            <button onClick={() => createAssetType(newAsset)}>Create Asset Type</button>
          </div>
          <div className="items-list">
            {assetTypes.map(type => (
              <div key={type.id} className="item-card">
                <h3>{type.name}</h3>
                <p>{type.description}</p>
                <small>Simulator: {type.simulator_name}</small>
                <button className="delete-btn" onClick={() => deleteItem('asset-types', type.id)}>Delete</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'assets' && (
        <div className="tab-content">
          <h2>Asset Management</h2>
          <div className="asset-creation">
            <div className="form-section">
              <input
                placeholder="Asset Name"
                value={newAsset.name || ''}
                onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })}
              />
              <select
                value={newAsset.asset_type_id || ''}
                onChange={(e) => setNewAsset({ ...newAsset, asset_type_id: e.target.value })}
              >
                <option value="">Select Asset Type</option>
                {assetTypes.map(type => (
                  <option key={type.id} value={type.id}>{type.name}</option>
                ))}
              </select>
              <input
                type="file"
                accept=".h5,.pkl,.joblib,.model"
                onChange={handleAssetModelUpload}
                className="file-input"
              />
              <p className="upload-hint">Upload ML model for this asset (.h5, .pkl, .joblib, .model)</p>
              <button
                className={isMarking ? 'marking' : ''}
                onClick={() => setIsMarking(!isMarking)}
              >
                {isMarking ? 'Click on Map to Mark Location' : 'Mark Location on Map'}
              </button>
              {newAsset.map_x && (
                <div>
                  <p>Location: ({newAsset.map_x}, {newAsset.map_y})</p>
                  <button onClick={createAsset}>Create Asset</button>
                </div>
              )}
            </div>

            {maps.length > 0 && (
              <div className="map-marking">
                <img
                  src={maps[0].path}
                  alt="Map for marking"
                  style={{
                    width: '600px',
                    height: 'auto',
                    cursor: isMarking ? 'crosshair' : 'default',
                    border: isMarking ? '3px solid #3b82f6' : '1px solid #ccc'
                  }}
                  onClick={handleMapClick}
                />
              </div>
            )}
          </div>

          <div className="assets-list">
            <h3>Existing Assets</h3>
            {assets.map(asset => (
              <div key={asset.id} className="asset-card">
                <h4>{asset.name}</h4>
                <p>Type: {asset.asset_type_name}</p>
                <p>Model: {asset.model_path || 'None'}</p>
                <p>Location: ({asset.map_x}, {asset.map_y})</p>
                <p>Status: {asset.status}</p>
                <button className="delete-btn" onClick={() => deleteItem('assets', asset.id)}>Delete</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;