import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { patientAPI, clinicalAPI, aiAPI } from '../api/client';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import toast from 'react-hot-toast';

const STATUS_OPTIONS = ['active', 'icu', 'emergency', 'discharged'];
const STATUS_COLORS = {
  active: { bg: '#22C55E20', color: '#4ADE80' },
  icu: { bg: '#DC262620', color: '#F87171' },
  emergency: { bg: '#F9731620', color: '#FB923C' },
  discharged: { bg: '#64748B20', color: '#94A3B8' },
};
const RISK_COLORS = { stable: '#22C55E', moderate: '#F97316', critical: '#DC2626', low: '#22C55E', medium: '#EAB308', high: '#F97316' };

const Tab = ({ label, active, onClick, badge }) => (
  <button onClick={onClick} style={{
    padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: active ? 700 : 400,
    background: active ? 'linear-gradient(135deg, #0EA5E9, #6366F1)' : 'transparent',
    color: active ? '#fff' : '#64748B',
    position: 'relative',
  }}>
    {label}
    {badge > 0 && <span style={{ position: 'absolute', top: 2, right: 4, background: '#DC2626', color: '#fff', borderRadius: '50%', width: 16, height: 16, fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>{badge}</span>}
  </button>
);

const Card = ({ children, style = {} }) => (
  <div style={{ background: 'linear-gradient(135deg, #0B1E3D, #071428)', border: '1px solid #0EA5E920', borderRadius: 16, padding: 20, ...style }}>
    {children}
  </div>
);

export default function PatientDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState(null);
  const [vitals, setVitals] = useState([]);
  const [diagnoses, setDiagnoses] = useState([]);
  const [labs, setLabs] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [aiAssessment, setAiAssessment] = useState(null);
  const [digitalTwin, setDigitalTwin] = useState(null);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  const [statusUpdating, setStatusUpdating] = useState(false);
  const [liveTimestamp, setLiveTimestamp] = useState(null);

  // Vitals form
  const [vitalForm, setVitalForm] = useState({ temperature: '', heart_rate: '', systolic_bp: '', diastolic_bp: '', oxygen_saturation: '', respiratory_rate: '', gcs_score: '' });
  const [vitalsLoading, setVitalsLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [pRes, vRes, dRes, lRes, aRes] = await Promise.all([
        patientAPI.get(id),
        patientAPI.getVitals(id, 20),
        clinicalAPI.getDiagnoses(id),
        clinicalAPI.getLabs(id),
        clinicalAPI.getAlerts(id),
      ]);
      setPatient(pRes.data);
      setVitals((vRes.data.vitals || []).reverse());
      setDiagnoses(dRes.data.diagnoses || []);
      setLabs(lRes.data.labs || []);
      setAlerts(aRes.data.alerts || []);
    } catch (e) { toast.error('Failed to load patient data'); }
    finally { setLoading(false); }
  }, [id]);

  const refreshVitals = useCallback(async () => {
    try {
      const vRes = await patientAPI.getVitals(id, 20);
      setVitals((vRes.data.vitals || []).reverse());
    } catch {}
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!id) return;
    const interval = setInterval(() => {
      refreshVitals();
      setLiveTimestamp(new Date().toLocaleTimeString());
    }, 3000);
    return () => clearInterval(interval);
  }, [id, refreshVitals]);

  const runAI = async () => {
    setPipelineLoading(true);
    try {
      const res = await aiAPI.runPipeline(id);
      setPipelineResult(res.data);
      setAiAssessment(res.data.stage_1_ai_ml || {});
      setDigitalTwin(res.data.stage_1_ai_ml?.digital_twin || null);
      toast.success('AI assessment complete');
      setActiveTab('ground_truth');
    } catch (e) { toast.error(e.response?.data?.detail || 'AI assessment failed'); }
    finally { setPipelineLoading(false); }
  };

  const recordVitals = async (e) => {
    e.preventDefault();
    setVitalsLoading(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(vitalForm).filter(([, v]) => v !== '').map(([k, v]) => [k, parseFloat(v) || parseInt(v)])
      );
      const res = await patientAPI.recordVitals(id, payload);
      toast.success(`Vitals recorded${res.data.is_critical ? ' — ⚠️ Critical values detected!' : ''}`);
      setVitalForm({ temperature: '', heart_rate: '', systolic_bp: '', diastolic_bp: '', oxygen_saturation: '', respiratory_rate: '', gcs_score: '' });
      loadData();
      if (res.data.ai_triggered) {
        setAiAssessment({ risk_assessment: { risk_level: res.data.risk_level, risk_score: res.data.risk_score } });
      }
    } catch (e) { toast.error('Failed to record vitals'); }
    finally { setVitalsLoading(false); }
  };

  const handleStatusChange = async (newStatus) => {
    setStatusUpdating(true);
    try {
      const res = await patientAPI.update(id, { status: newStatus });
      if (newStatus === 'discharged') {
        toast.success(`Patient discharged — redirecting to reports`);
        navigate(`/reports?patientId=${id}&name=${encodeURIComponent(patient?.full_name || '')}`);
        return;
      } else if (newStatus === 'icu') {
        toast.success(`Patient added to ICU monitoring system`, { duration: 4000 });
      } else {
        toast.success(`Status changed to ${newStatus}`);
      }
      setPatient(p => ({ ...p, status: newStatus }));
      loadData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update status');
    } finally {
      setStatusUpdating(false);
    }
  };

  if (loading) return <div style={{ color: '#64748B', padding: 40, textAlign: 'center' }}>Loading patient...</div>;
  if (!patient) return <div style={{ color: '#F87171', padding: 40 }}>Patient not found</div>;

  const latestVital = vitals[vitals.length - 1] || {};
  const risk = aiAssessment?.risk_assessment;
  const riskColor = risk ? RISK_COLORS[risk.risk_level] || '#0EA5E9' : '#0EA5E9';
  const unackAlerts = alerts.filter(a => !a.is_acknowledged).length;

  // Prepare chart data
  const vitalsChartData = vitals.slice(-10).map((v, i) => ({
    t: i + 1,
    hr: v.heart_rate,
    spo2: v.oxygen_saturation,
    bp_s: v.systolic_bp,
    temp: v.temperature,
  }));

  return (
    <div>
      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
      {/* Patient header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 60, height: 60, borderRadius: 16, background: 'linear-gradient(135deg, #0EA5E940, #6366F140)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>
            {patient.gender === 'Female' ? '👩' : '👨'}
          </div>
          <div>
            <h1 style={{ color: '#F1F5F9', fontSize: 24, fontWeight: 700, margin: 0 }}>{patient.full_name}</h1>
            <p style={{ color: '#475569', fontSize: 13, margin: '4px 0 0' }}>
              {patient.patient_id} · {patient.gender} · {patient.blood_type || 'Unknown blood type'} · Ward: {patient.ward || 'N/A'} · Bed: {patient.bed_number || 'N/A'}
            </p>
            {patient.allergies?.length > 0 && (
              <p style={{ color: '#F87171', fontSize: 11, margin: '4px 0 0' }}>
                ⚠️ Allergies: {patient.allergies.join(', ')}
              </p>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {/* Status selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#64748B', fontSize: 11 }}>Status:</span>
            <select value={patient.status || 'active'} onChange={e => handleStatusChange(e.target.value)}
              disabled={statusUpdating}
              style={{
                padding: '6px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer', outline: 'none',
                background: (STATUS_COLORS[patient.status] || STATUS_COLORS.active).bg,
                color: (STATUS_COLORS[patient.status] || STATUS_COLORS.active).color,
                border: `1px solid ${(STATUS_COLORS[patient.status] || STATUS_COLORS.active).color}40`,
              }}>
              {STATUS_OPTIONS.map(s => (
                <option key={s} value={s} style={{ background: '#0B1E3D', color: STATUS_COLORS[s].color }}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            {statusUpdating && <span style={{ color: '#64748B', fontSize: 10 }}>...</span>}
          </div>

          {/* LIVE indicator */}
          {liveTimestamp && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 20, background: '#22C55E20', border: '1px solid #22C55E40' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22C55E', animation: liveTimestamp ? 'pulse 1.5s infinite' : 'none' }} />
              <span style={{ color: '#4ADE80', fontSize: 11, fontWeight: 700 }}>LIVE</span>
              <span style={{ color: '#4ADE8080', fontSize: 10 }}>{liveTimestamp}</span>
            </div>
          )}

          {risk && (
            <div style={{ padding: '8px 16px', borderRadius: 10, background: riskColor + '20', border: `1px solid ${riskColor}40`, textAlign: 'center' }}>
              <div style={{ color: riskColor, fontWeight: 800, fontSize: 16 }}>{risk.risk_level?.toUpperCase()}</div>
              <div style={{ color: '#64748B', fontSize: 11 }}>AI Risk · {(risk.risk_score * 100).toFixed(0)}%</div>
            </div>
          )}
          <button onClick={runAI} disabled={pipelineLoading}
            style={{ padding: '10px 20px', borderRadius: 10, background: pipelineLoading ? '#1E3A5F' : 'linear-gradient(135deg, #6366F1, #8B5CF6)', color: '#fff', fontWeight: 700, border: 'none', cursor: pipelineLoading ? 'not-allowed' : 'pointer', fontSize: 13 }}>
            {pipelineLoading ? '⏳ Running Analysis...' : '🎯 Run AI Assessment'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, background: '#0B1E3D', padding: 6, borderRadius: 12, width: 'fit-content' }}>
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'vitals', label: 'Vitals' },
          { id: 'diagnoses', label: 'Diagnoses' },
          { id: 'ai', label: '🧠 AI Analysis' },
          { id: 'twin', label: '🔬 Digital Twin' },
          { id: 'ground_truth', label: '🎯 Ground Truth' },
          { id: 'alerts', label: 'Alerts', badge: unackAlerts },
        ].map(t => <Tab key={t.id} label={t.label} active={activeTab === t.id} onClick={() => setActiveTab(t.id)} badge={t.badge} />)}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <div>
          {/* Discharged banner */}
          {patient.status === 'discharged' && (
            <div style={{ marginBottom: 16, padding: '20px 24px', borderRadius: 16, background: 'linear-gradient(135deg, #64748B20, #47556920)', border: '2px solid #64748B40', textAlign: 'center' }}>
              <div style={{ fontSize: 40, marginBottom: 8 }}>📋</div>
              <h3 style={{ color: '#94A3B8', fontSize: 18, fontWeight: 700, margin: '0 0 4px' }}>Patient Discharged</h3>
              <p style={{ color: '#64748B', fontSize: 13, margin: 0 }}>This patient has been discharged. No vitals are being monitored.</p>
              <button onClick={() => navigate(`/reports?patientId=${id}&name=${encodeURIComponent(patient?.full_name || '')}`)}
                style={{ marginTop: 12, padding: '8px 20px', borderRadius: 10, background: 'linear-gradient(135deg, #0EA5E9, #6366F1)', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer', fontSize: 13 }}>
                📄 View Discharge Reports
              </button>
            </div>
          )}

          {patient.status !== 'discharged' ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Latest vitals */}
          <Card>
            <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>LATEST VITALS</h3>
            {Object.keys(latestVital).length === 0 ? (
              <p style={{ color: '#475569', fontSize: 13 }}>No vitals recorded yet</p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {[
                  { label: '🌡️ Temperature', val: latestVital.temperature ? `${latestVital.temperature}°C` : '—', alert: latestVital.temperature < 35 || latestVital.temperature > 40 },
                  { label: '💓 Heart Rate', val: latestVital.heart_rate ? `${latestVital.heart_rate} bpm` : '—', alert: latestVital.heart_rate < 40 || latestVital.heart_rate > 150 },
                  { label: '🩸 Blood Pressure', val: latestVital.systolic_bp ? `${latestVital.systolic_bp}/${latestVital.diastolic_bp} mmHg` : '—', alert: latestVital.systolic_bp > 180 || latestVital.systolic_bp < 80 },
                  { label: '💨 SpO2', val: latestVital.oxygen_saturation ? `${latestVital.oxygen_saturation}%` : '—', alert: latestVital.oxygen_saturation < 90 },
                  { label: '🫁 Resp Rate', val: latestVital.respiratory_rate ? `${latestVital.respiratory_rate}/min` : '—', alert: false },
                  { label: '🧠 GCS', val: latestVital.gcs_score || '—', alert: latestVital.gcs_score < 13 },
                ].map(({ label, val, alert }) => (
                  <div key={label} style={{ padding: '10px 12px', borderRadius: 10, background: alert ? '#DC262610' : '#0EA5E908', border: `1px solid ${alert ? '#DC262630' : '#0EA5E915'}` }}>
                    <div style={{ color: '#475569', fontSize: 10 }}>{label}</div>
                    <div style={{ color: alert ? '#F87171' : '#CBD5E1', fontWeight: 700, fontSize: 16 }}>{val}</div>
                    {alert && <div style={{ color: '#F87171', fontSize: 9 }}>⚠️ CRITICAL</div>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Conditions */}
          <Card>
            <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>ACTIVE CONDITIONS</h3>
            {diagnoses.length === 0 ? (
              <p style={{ color: '#475569', fontSize: 13 }}>No diagnoses recorded</p>
            ) : (
              diagnoses.slice(0, 5).map(d => (
                <div key={d.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #0EA5E910' }}>
                  <div>
                    <div style={{ color: '#CBD5E1', fontSize: 13 }}>{d.condition_name}</div>
                    <div style={{ color: '#475569', fontSize: 11 }}>{d.icd_code || 'No ICD code'}</div>
                  </div>
                  <span style={{
                    padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700,
                    background: { critical: '#DC262620', severe: '#F9731620', moderate: '#EAB30820', mild: '#22C55E20' }[d.severity] || '#64748B20',
                    color: { critical: '#F87171', severe: '#FB923C', moderate: '#FDE047', mild: '#4ADE80' }[d.severity] || '#94A3B8',
                  }}>{d.severity?.toUpperCase()}</span>
                </div>
              ))
            )}
          </Card>

          {/* Vitals trend chart */}
          <Card style={{ gridColumn: '1 / -1' }}>
            <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>VITALS TREND (LAST 10 READINGS)</h3>
            {vitalsChartData.length < 2 ? (
              <p style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>Record more vitals to see trends</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={vitalsChartData}>
                  <XAxis dataKey="t" stroke="#1E3A5F" tick={{ fill: '#475569', fontSize: 10 }} />
                  <YAxis stroke="#1E3A5F" tick={{ fill: '#475569', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#0B1E3D', border: '1px solid #0EA5E930', borderRadius: 8, color: '#94A3B8', fontSize: 12 }} />
                  <ReferenceLine y={60} stroke="#DC262640" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="hr" stroke="#0EA5E9" strokeWidth={2} dot={false} name="Heart Rate" />
                  <Line type="monotone" dataKey="spo2" stroke="#22C55E" strokeWidth={2} dot={false} name="SpO2" />
                  <Line type="monotone" dataKey="bp_s" stroke="#F97316" strokeWidth={2} dot={false} name="Systolic BP" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
        ) : null}
        </div>
      )}

      {activeTab === 'vitals' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Record form */}
          <Card>
            <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>RECORD NEW VITALS</h3>
            <form onSubmit={recordVitals}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {[
                  { key: 'temperature', label: 'Temperature (°C)', placeholder: '36.8' },
                  { key: 'heart_rate', label: 'Heart Rate (bpm)', placeholder: '72' },
                  { key: 'systolic_bp', label: 'Systolic BP', placeholder: '120' },
                  { key: 'diastolic_bp', label: 'Diastolic BP', placeholder: '80' },
                  { key: 'oxygen_saturation', label: 'SpO2 (%)', placeholder: '98' },
                  { key: 'respiratory_rate', label: 'Resp. Rate (/min)', placeholder: '16' },
                  { key: 'gcs_score', label: 'GCS Score (3-15)', placeholder: '15' },
                ].map(({ key, label, placeholder }) => (
                  <div key={key} style={{ marginBottom: 8 }}>
                    <label style={{ color: '#64748B', fontSize: 10, fontWeight: 600, display: 'block', marginBottom: 4 }}>{label}</label>
                    <input type="number" step="any" placeholder={placeholder} value={vitalForm[key]}
                      onChange={e => setVitalForm(f => ({ ...f, [key]: e.target.value }))}
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 8, background: '#060E1A', border: '1px solid #0EA5E920', color: '#F1F5F9', fontSize: 13, outline: 'none', boxSizing: 'border-box' }} />
                  </div>
                ))}
              </div>
              <button type="submit" disabled={vitalsLoading}
                style={{ width: '100%', padding: '10px', borderRadius: 10, marginTop: 8, background: 'linear-gradient(135deg, #0EA5E9, #6366F1)', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer' }}>
                {vitalsLoading ? 'Recording...' : '📋 Record Vitals + Trigger AI'}
              </button>
            </form>
          </Card>

          {/* Vitals history */}
          <Card>
            <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>VITALS HISTORY</h3>
            <div style={{ maxHeight: 380, overflow: 'auto' }}>
              {vitals.length === 0 ? (
                <p style={{ color: '#475569', fontSize: 13 }}>No vitals recorded</p>
              ) : [...vitals].reverse().map(v => (
                <div key={v.id} style={{ padding: '10px 0', borderBottom: '1px solid #0EA5E910' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ color: v.is_critical ? '#F87171' : '#64748B', fontSize: 11 }}>
                      {v.is_critical && '⚠️ '}{new Date(v.recorded_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {[
                      v.temperature && `🌡️ ${v.temperature}°C`,
                      v.heart_rate && `💓 ${v.heart_rate} bpm`,
                      v.systolic_bp && `🩸 ${v.systolic_bp}/${v.diastolic_bp}`,
                      v.oxygen_saturation && `💨 ${v.oxygen_saturation}%`,
                    ].filter(Boolean).map(s => (
                      <span key={s} style={{ color: '#94A3B8', fontSize: 11, background: '#0EA5E910', padding: '2px 6px', borderRadius: 4 }}>{s}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'diagnoses' && (
        <Card>
          <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>DIAGNOSIS HISTORY</h3>
          {diagnoses.length === 0 ? (
            <p style={{ color: '#475569', fontSize: 13 }}>No diagnoses recorded</p>
          ) : (
            diagnoses.map(d => (
              <div key={d.id} style={{ padding: '14px', borderRadius: 10, background: '#060E1A', border: '1px solid #0EA5E915', marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div>
                    <span style={{ color: '#CBD5E1', fontWeight: 700, fontSize: 14 }}>{d.condition_name}</span>
                    {d.icd_code && <span style={{ color: '#475569', fontSize: 11, marginLeft: 8 }}>[{d.icd_code}]</span>}
                  </div>
                  <span style={{
                    padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                    background: { critical: '#DC262620', severe: '#F9731620', moderate: '#EAB30820', mild: '#22C55E20' }[d.severity] || '#64748B20',
                    color: { critical: '#F87171', severe: '#FB923C', moderate: '#FDE047', mild: '#4ADE80' }[d.severity] || '#94A3B8',
                  }}>{d.severity?.toUpperCase()}</span>
                </div>
                {d.description && <p style={{ color: '#64748B', fontSize: 12, margin: '0 0 6px' }}>{d.description}</p>}
                {d.treatment_plan && <p style={{ color: '#475569', fontSize: 12, margin: 0 }}>📋 {d.treatment_plan}</p>}
              </div>
            ))
          )}
        </Card>
      )}

      {activeTab === 'ai' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {!aiAssessment ? (
            <Card style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🧠</div>
              <p style={{ color: '#64748B', fontSize: 14 }}>No AI assessment yet. Click "Run AI Assessment" to analyze this patient.</p>
            </Card>
          ) : (
            <>
              {/* Risk score card */}
              <Card style={{ gridColumn: '1 / -1' }}>
                <div style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ textAlign: 'center', padding: '16px 24px', borderRadius: 14, background: (riskColor) + '15', border: `1px solid ${riskColor}30` }}>
                    <div style={{ color: riskColor, fontSize: 40, fontWeight: 800 }}>{((risk?.risk_score || 0) * 100).toFixed(0)}%</div>
                    <div style={{ color: riskColor, fontSize: 14, fontWeight: 700 }}>{risk?.risk_level?.toUpperCase()} RISK</div>
                    <div style={{ color: '#64748B', fontSize: 11, marginTop: 4 }}>Confidence: {((risk?.confidence_score || 0) * 100).toFixed(0)}%</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 10px' }}>AI CLINICAL SUMMARY</h3>
                    <p style={{ color: '#CBD5E1', fontSize: 13, lineHeight: 1.7, margin: 0, padding: '12px 16px', background: '#0EA5E908', borderRadius: 10, border: '1px solid #0EA5E915' }}>
                      {aiAssessment.clinical_summary || 'Summary not available'}
                    </p>
                    {risk?.requires_human_review && (
                      <div style={{ marginTop: 10, padding: '8px 14px', background: '#EAB30820', border: '1px solid #EAB30840', borderRadius: 8, color: '#FDE047', fontSize: 12 }}>
                        ⏳ Human review required — AI confidence below threshold
                      </div>
                    )}
                  </div>
                </div>
              </Card>

              {/* Contributing factors */}
              <Card>
                <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>CONTRIBUTING FACTORS</h3>
                {Object.entries(risk?.contributing_factors || {}).map(([factor, weight]) => (
                  <div key={factor} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: '#94A3B8', fontSize: 12 }}>{factor.replace(/_/g, ' ')}</span>
                      <span style={{ color: '#0EA5E9', fontSize: 11, fontWeight: 700 }}>{(weight * 100).toFixed(1)}%</span>
                    </div>
                    <div style={{ height: 4, background: '#1E3A5F', borderRadius: 2 }}>
                      <div style={{ height: '100%', width: `${Math.min(weight * 300, 100)}%`, background: `linear-gradient(90deg, #0EA5E9, #6366F1)`, borderRadius: 2, transition: 'width 0.6s ease' }} />
                    </div>
                  </div>
                ))}
              </Card>

              {/* Explanations & Recommendations */}
              <Card>
                <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>CLINICAL REASONING</h3>
                {(risk?.explanation || []).map((e, i) => (
                  <div key={i} style={{ padding: '6px 10px', marginBottom: 6, background: '#F9731608', border: '1px solid #F9731625', borderRadius: 8, color: '#CBD5E1', fontSize: 12 }}>
                    ⚡ {e}
                  </div>
                ))}
                {(risk?.contradictions || []).length > 0 && (
                  <>
                    <div style={{ color: '#64748B', fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', margin: '12px 0 8px' }}>MITIGATING FACTORS</div>
                    {risk.contradictions.map((c, i) => (
                      <div key={i} style={{ padding: '6px 10px', marginBottom: 6, background: '#22C55E08', border: '1px solid #22C55E25', borderRadius: 8, color: '#94A3B8', fontSize: 12 }}>
                        ✓ {c}
                      </div>
                    ))}
                  </>
                )}
                <div style={{ color: '#64748B', fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', margin: '12px 0 8px' }}>RECOMMENDATIONS</div>
                {(risk?.recommendations || []).map((r, i) => (
                  <div key={i} style={{ padding: '6px 10px', marginBottom: 6, background: '#0EA5E908', border: '1px solid #0EA5E920', borderRadius: 8, color: '#94A3B8', fontSize: 12 }}>
                    → {r}
                  </div>
                ))}
              </Card>

              {/* Anomaly detection */}
              {aiAssessment.anomaly_detection && (
                <Card style={{ gridColumn: '1 / -1' }}>
                  <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>
                    ANOMALY DETECTION — Score: {(aiAssessment.anomaly_detection.anomaly_score * 100).toFixed(0)}%
                    {aiAssessment.anomaly_detection.is_anomaly && <span style={{ color: '#F87171', marginLeft: 8 }}>⚠️ ANOMALIES DETECTED</span>}
                  </h3>
                  {(aiAssessment.anomaly_detection.anomalies || []).length === 0 ? (
                    <p style={{ color: '#4ADE80', fontSize: 13 }}>✓ No clinical anomalies detected</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
                      {aiAssessment.anomaly_detection.anomalies.map((a, i) => (
                        <div key={i} style={{ padding: '10px 14px', background: '#DC262610', border: '1px solid #DC262630', borderRadius: 10 }}>
                          <div style={{ color: '#F87171', fontWeight: 700, fontSize: 12 }}>{a.type?.replace(/_/g, ' ').toUpperCase()}</div>
                          <div style={{ color: '#94A3B8', fontSize: 12, marginTop: 4 }}>{a.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'twin' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {!digitalTwin ? (
            <Card style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🔬</div>
              <p style={{ color: '#64748B', fontSize: 14 }}>Digital twin not initialized. Run AI assessment first.</p>
            </Card>
          ) : (
            <>
              <Card>
                <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>PHYSIOLOGICAL STATE</h3>
                <div style={{ color: '#CBD5E1', fontSize: 13 }}>
                  <div style={{ marginBottom: 8 }}>Vitals Trend: <span style={{ color: digitalTwin.physiological_state?.vitals_trend === 'improving' ? '#4ADE80' : digitalTwin.physiological_state?.vitals_trend === 'worsening' ? '#F87171' : '#FDE047', fontWeight: 700 }}>{(digitalTwin.physiological_state?.vitals_trend || 'stable').toUpperCase()}</span></div>
                  <div style={{ marginBottom: 8 }}>Lab Status: <span style={{ color: digitalTwin.physiological_state?.lab_status === 'critical' ? '#F87171' : '#4ADE80', fontWeight: 700 }}>{(digitalTwin.physiological_state?.lab_status || 'normal').toUpperCase()}</span></div>
                  <div>Data Freshness: {digitalTwin.physiological_state?.data_freshness_minutes < 60 ? `${digitalTwin.physiological_state?.data_freshness_minutes} min ago` : 'Stale'}</div>
                </div>
              </Card>

              <Card>
                <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>DISEASE TRAJECTORY</h3>
                {(digitalTwin.disease_trajectory || []).map(t => (
                  <div key={t.hours_from_now} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #0EA5E910' }}>
                    <span style={{ color: '#64748B', fontSize: 12 }}>+{t.hours_from_now}h</span>
                    <div style={{ flex: 1, margin: '0 12px', height: 4, background: '#1E3A5F', borderRadius: 2 }}>
                      <div style={{ height: '100%', width: `${t.projected_risk_score * 100}%`, background: RISK_COLORS[t.projected_risk_level] || '#0EA5E9', borderRadius: 2 }} />
                    </div>
                    <span style={{ color: RISK_COLORS[t.projected_risk_level], fontSize: 11, fontWeight: 700, minWidth: 50 }}>{(t.projected_risk_score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </Card>

              <Card style={{ gridColumn: '1 / -1' }}>
                <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>🔮 WHAT-IF SCENARIOS</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
                  {(digitalTwin.what_if_scenarios || []).map(s => (
                    <div key={s.scenario} style={{ padding: '14px', borderRadius: 12, background: '#060E1A', border: '1px solid #0EA5E915' }}>
                      <div style={{ color: '#CBD5E1', fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{s.description}</div>
                      <div style={{ color: s.projected_risk_change < 0 ? '#4ADE80' : '#F87171', fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
                        {s.projected_risk_change < 0 ? '↓ ' : '↑ '}{Math.abs(s.projected_risk_change * 100).toFixed(0)}% risk in {s.timeframe_hours}h
                      </div>
                      {s.interventions?.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {s.interventions.map(inv => (
                            <span key={inv} style={{ padding: '2px 8px', background: '#0EA5E910', border: '1px solid #0EA5E920', borderRadius: 20, color: '#64748B', fontSize: 10 }}>{inv}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}
        </div>
      )}

      {activeTab === 'ground_truth' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {!pipelineResult ? (
            <Card style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🎯</div>
              <p style={{ color: '#64748B', fontSize: 14 }}>No pipeline results yet. Click "Run AI Assessment" to run the full 3-stage analysis.</p>
            </Card>
          ) : (
            <>
              {/* Stage 3: Ground Truth (top-level summary) */}
              <Card style={{ gridColumn: '1 / -1', border: '2px solid #22C55E40' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                  <div style={{ fontSize: 32 }}>🎯</div>
                  <div>
                    <h3 style={{ color: '#4ADE80', fontSize: 14, fontWeight: 700, letterSpacing: '0.5px', margin: 0 }}>STAGE 3 — GEN AI GROUND TRUTH</h3>
                    <p style={{ color: '#64748B', fontSize: 11, margin: '2px 0 0' }}>Validated against clinical guidelines · Evidence-based reality check</p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                  {[
                    { label: 'AI/ML Accuracy', value: pipelineResult.stage_3_ground_truth?.ai_ml_report_accuracy, color: '#0EA5E9' },
                    { label: 'LLM Quality', value: pipelineResult.stage_3_ground_truth?.llm_reasoning_quality, color: '#8B5CF6' },
                    { label: 'Ground Truth Confidence', value: pipelineResult.stage_3_ground_truth?.overall_confidence, color: '#22C55E' },
                  ].map(m => (
                    <div key={m.label} style={{ flex: 1, padding: '12px 16px', background: '#0EA5E908', borderRadius: 10, border: '1px solid #0EA5E915', textAlign: 'center' }}>
                      <div style={{ color: m.color, fontSize: 28, fontWeight: 800 }}>{m.value ? `${(m.value * 100).toFixed(0)}%` : '—'}</div>
                      <div style={{ color: '#64748B', fontSize: 11, fontWeight: 600, marginTop: 4 }}>{m.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{ padding: '14px 16px', background: '#060E1A', borderRadius: 10, border: '1px solid #0EA5E915' }}>
                  <p style={{ color: '#CBD5E1', fontSize: 13, lineHeight: 1.7, margin: 0 }}>
                    {pipelineResult.stage_3_ground_truth?.ground_truth_summary || 'Ground truth summary not available'}
                  </p>
                </div>
              </Card>

              {/* Discrepancies */}
              {(pipelineResult.stage_3_ground_truth?.discrepancies_found || []).length > 0 && (
                <Card>
                  <h3 style={{ color: '#F87171', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>⚠️ DISCREPANCIES FOUND</h3>
                  {pipelineResult.stage_3_ground_truth.discrepancies_found.map((d, i) => (
                    <div key={i} style={{ padding: '8px 12px', marginBottom: 6, background: '#DC262610', border: '1px solid #DC262630', borderRadius: 8, color: '#F87171', fontSize: 12 }}>
                      ⚡ {d}
                    </div>
                  ))}
                </Card>
              )}

              {/* Corrected Recommendations */}
              <Card>
                <h3 style={{ color: '#4ADE80', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>✓ CORRECTED RECOMMENDATIONS</h3>
                {(pipelineResult.stage_3_ground_truth?.corrected_recommendations || []).length === 0 ? (
                  <p style={{ color: '#64748B', fontSize: 13 }}>No corrections needed — AI/ML recommendations align with guidelines</p>
                ) : (
                  pipelineResult.stage_3_ground_truth.corrected_recommendations.map((r, i) => (
                    <div key={i} style={{ padding: '8px 12px', marginBottom: 6, background: '#22C55E10', border: '1px solid #22C55E30', borderRadius: 8, color: '#94A3B8', fontSize: 12 }}>
                      → {r}
                    </div>
                  ))
                )}
              </Card>

              {/* Guideline Citations */}
              <Card style={{ gridColumn: '1 / -1' }}>
                <h3 style={{ color: '#EAB308', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>📋 GUIDELINE CITATIONS</h3>
                {(pipelineResult.stage_3_ground_truth?.guideline_citations || []).length === 0 ? (
                  <p style={{ color: '#64748B', fontSize: 13 }}>No guideline citations recorded</p>
                ) : (
                  pipelineResult.stage_3_ground_truth.guideline_citations.map((c, i) => (
                    <div key={i} style={{ padding: '8px 12px', marginBottom: 6, background: '#EAB30810', border: '1px solid #EAB30830', borderRadius: 8, color: '#FDE047', fontSize: 11 }}>
                      📜 {c}
                    </div>
                  ))
                )}
              </Card>

              {/* Stage 1: AI/ML Report (collapsible) */}
              <Card style={{ gridColumn: '1 / -1' }}>
                <h3 style={{ color: '#0EA5E9', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>
                  📊 STAGE 1 — AI/ML MODEL REPORT
                  <span style={{ color: '#64748B', fontWeight: 400, marginLeft: 8, fontSize: 11 }}>
                    Risk: {(pipelineResult.stage_1_ai_ml?.risk_assessment?.risk_score || 0 * 100).toFixed(0)}% · {pipelineResult.stage_1_ai_ml?.risk_assessment?.risk_level || '—'}
                  </span>
                </h3>
                <div style={{ padding: '12px 16px', background: '#060E1A', borderRadius: 10, border: '1px solid #0EA5E915', marginBottom: 10 }}>
                  <p style={{ color: '#94A3B8', fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                    {pipelineResult.stage_1_ai_ml?.clinical_summary || 'Summary not available'}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(pipelineResult.stage_1_ai_ml?.risk_assessment?.explanation || []).slice(0, 4).map((e, i) => (
                    <span key={i} style={{ padding: '3px 10px', background: '#F9731610', border: '1px solid #F9731630', borderRadius: 20, color: '#94A3B8', fontSize: 11 }}>
                      ⚡ {e}
                    </span>
                  ))}
                </div>
              </Card>

              {/* Stage 2: LLM Analysis */}
              {pipelineResult.stage_2_llm?.clinical_summary && (
                <Card style={{ gridColumn: '1 / -1' }}>
                  <h3 style={{ color: '#8B5CF6', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 14px' }}>
                    🧠 STAGE 2 — LLM CLINICAL ANALYSIS
                  </h3>
                  <div style={{ padding: '12px 16px', background: '#060E1A', borderRadius: 10, border: '1px solid #0EA5E915' }}>
                    <p style={{ color: '#CBD5E1', fontSize: 13, lineHeight: 1.7, margin: 0 }}>
                      {pipelineResult.stage_2_llm.clinical_summary}
                    </p>
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'alerts' && (
        <Card>
          <h3 style={{ color: '#94A3B8', fontSize: 12, fontWeight: 700, letterSpacing: '0.5px', margin: '0 0 16px' }}>
            CLINICAL ALERTS {unackAlerts > 0 && <span style={{ color: '#F87171' }}>({unackAlerts} unacknowledged)</span>}
          </h3>
          {alerts.length === 0 ? (
            <p style={{ color: '#4ADE80', fontSize: 14, textAlign: 'center', padding: '20px 0' }}>✓ No alerts for this patient</p>
          ) : (
            alerts.map(a => (
              <div key={a.id} style={{ padding: '14px', borderRadius: 10, marginBottom: 10, background: '#060E1A', border: `1px solid ${a.severity === 'critical' ? '#DC262630' : a.severity === 'warning' ? '#F9731630' : '#0EA5E920'}`, opacity: a.is_acknowledged ? 0.6 : 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ color: a.severity === 'critical' ? '#F87171' : a.severity === 'warning' ? '#FB923C' : '#38BDF8', fontWeight: 700, fontSize: 13 }}>{a.title}</span>
                    <p style={{ color: '#94A3B8', fontSize: 12, margin: '4px 0 0' }}>{a.message}</p>
                    <p style={{ color: '#475569', fontSize: 11, margin: '4px 0 0' }}>{new Date(a.created_at).toLocaleString()}</p>
                  </div>
                  {!a.is_acknowledged && (
                    <button onClick={async () => {
                      await clinicalAPI.acknowledgeAlert(a.id);
                      loadData();
                      toast.success('Alert acknowledged');
                    }} style={{ padding: '6px 14px', borderRadius: 8, background: '#22C55E20', color: '#4ADE80', border: '1px solid #22C55E40', cursor: 'pointer', fontSize: 12 }}>
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </Card>
      )}
    </div>
  );
}
