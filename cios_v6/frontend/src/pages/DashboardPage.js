import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientAPI, aiAPI } from '../api/client';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const Card = ({ children, style = {} }) => (
  <div style={{
    background: 'linear-gradient(135deg, #0B1E3D, #071428)',
    border: '1px solid #0EA5E920', borderRadius: 16, padding: 20,
    ...style
  }}>{children}</div>
);

const StatCard = ({ icon, label, value, sub, color = '#0EA5E9', delta }) => (
  <Card>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <p style={{ color: '#64748B', fontSize: 12, fontWeight: 600, letterSpacing: '0.5px', margin: '0 0 8px' }}>{label.toUpperCase()}</p>
        <h2 style={{ color: '#F1F5F9', fontSize: 32, fontWeight: 700, margin: 0, lineHeight: 1 }}>{value}</h2>
        {sub && <p style={{ color: '#475569', fontSize: 12, margin: '6px 0 0' }}>{sub}</p>}
        {delta !== undefined && (
          <span style={{ fontSize: 11, color: delta >= 0 ? '#4ADE80' : '#F87171', fontWeight: 600 }}>
            {delta >= 0 ? '↑' : '↓'} {Math.abs(delta)}% from yesterday
          </span>
        )}
      </div>
      <div style={{
        width: 44, height: 44, borderRadius: 12,
        background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22, border: `1px solid ${color}30`,
      }}>{icon}</div>
    </div>
  </Card>
);

const RISK_COLORS = { stable: '#22C55E', moderate: '#F97316', critical: '#DC2626', low: '#22C55E', medium: '#EAB308', high: '#F97316' };

export default function DashboardPage() {
  const ICU_URL = process.env.REACT_APP_ICU_URL || 'http://localhost:5174';
  const [stats, setStats] = useState(null);
  const [patients, setPatients] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, patientsRes, reviewsRes] = await Promise.all([
          patientAPI.stats(),
          patientAPI.list({ limit: 5 }),
          aiAPI.getPendingReviews(),
        ]);
        setStats(statsRes.data);
        setPatients(patientsRes.data.patients || []);
        setReviews(reviewsRes.data.pending || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  // Mock trend data for demo
  const trendData = Array.from({ length: 12 }, (_, i) => ({
    hour: `${i * 2}:00`,
    admissions: Math.floor(Math.random() * 8 + 2),
    critical: Math.floor(Math.random() * 3),
  }));

  const riskDistData = [
    { name: 'Low', value: 45, color: '#22C55E' },
    { name: 'Medium', value: 30, color: '#EAB308' },
    { name: 'High', value: 18, color: '#F97316' },
    { name: 'Critical', value: 7, color: '#DC2626' },
  ];

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
      <div style={{ color: '#0EA5E9', fontSize: 14 }}>Loading CIOS Dashboard...</div>
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ color: '#F1F5F9', fontSize: 28, fontWeight: 700, margin: 0 }}>
          Clinical Intelligence Dashboard
        </h1>
        <p style={{ color: '#475569', fontSize: 14, margin: '4px 0 0' }}>
          Real-time hospital monitoring · AI-powered insights · {new Date().toLocaleTimeString()}
        </p>
        <div style={{ marginTop: 12 }}>
          <button onClick={() => window.open(ICU_URL, '_blank')}
            style={{ padding: '8px 12px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#0EA5E9', color: '#fff', fontWeight: 700 }}>
            Open ICU Monitoring System
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatCard icon="👥" label="Total Patients" value={stats?.total_patients ?? '—'} sub="All registered" color="#0EA5E9" delta={3} />
        <StatCard icon="🏥" label="Active" value={stats?.active_patients ?? '—'} sub="Currently admitted" color="#22C55E" />
        <StatCard icon="🚨" label="ICU" value={stats?.icu_patients ?? '—'} sub="Intensive care" color="#DC2626" />
        <StatCard icon="🧠" label="High Risk" value={stats?.high_risk_predictions ?? '—'} sub="AI-flagged" color="#F97316" delta={-2} />
        <StatCard icon="⏳" label="Pending Reviews" value={stats?.pending_reviews ?? '—'} sub="Awaiting physician" color="#EAB308" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* Admission trend */}
        <Card>
          <h3 style={{ color: '#94A3B8', fontSize: 13, fontWeight: 600, letterSpacing: '0.5px', margin: '0 0 16px' }}>
            24H ADMISSION TREND
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="admGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0EA5E9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0EA5E9" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="critGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#DC2626" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#DC2626" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" stroke="#1E3A5F" tick={{ fill: '#475569', fontSize: 11 }} />
              <YAxis stroke="#1E3A5F" tick={{ fill: '#475569', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#0B1E3D', border: '1px solid #0EA5E930', borderRadius: 8, color: '#94A3B8' }} />
              <Area type="monotone" dataKey="admissions" stroke="#0EA5E9" fill="url(#admGrad)" strokeWidth={2} name="Admissions" />
              <Area type="monotone" dataKey="critical" stroke="#DC2626" fill="url(#critGrad)" strokeWidth={2} name="Critical" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* Risk distribution */}
        <Card>
          <h3 style={{ color: '#94A3B8', fontSize: 13, fontWeight: 600, letterSpacing: '0.5px', margin: '0 0 16px' }}>
            AI RISK DISTRIBUTION
          </h3>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={riskDistData} cx="50%" cy="50%" innerRadius={40} outerRadius={65}
                dataKey="value" strokeWidth={0}>
                {riskDistData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} opacity={0.85} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#0B1E3D', border: '1px solid #0EA5E930', borderRadius: 8, color: '#94A3B8' }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
            {riskDistData.map(({ name, color, value }) => (
              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                <span style={{ color: '#64748B', fontSize: 11 }}>{name} {value}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Bottom row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Recent patients */}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ color: '#94A3B8', fontSize: 13, fontWeight: 600, letterSpacing: '0.5px', margin: 0 }}>
              RECENT PATIENTS
            </h3>
            <button onClick={() => navigate('/patients')}
              style={{ background: 'none', border: 'none', color: '#0EA5E9', fontSize: 12, cursor: 'pointer' }}>
              View all →
            </button>
          </div>
          {patients.length === 0 ? (
            <p style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>No patients yet</p>
          ) : (
            patients.map(p => (
              <div key={p.id} onClick={() => navigate(`/patients/${p.id}`)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 0', borderBottom: '1px solid #0EA5E910',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#0EA5E908'}
                onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'linear-gradient(135deg, #0EA5E930, #6366F130)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
                  }}>👤</div>
                  <div>
                    <div style={{ color: '#CBD5E1', fontSize: 13, fontWeight: 600 }}>{p.full_name}</div>
                    <div style={{ color: '#475569', fontSize: 11 }}>{p.patient_id}</div>
                  </div>
                </div>
                <span style={{
                  padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                  background: p.status === 'icu' ? '#DC262620' : p.status === 'active' ? '#22C55E20' : '#64748B20',
                  color: p.status === 'icu' ? '#F87171' : p.status === 'active' ? '#4ADE80' : '#94A3B8',
                }}>{p.status?.toUpperCase()}</span>
              </div>
            ))
          )}
        </Card>

        {/* Pending AI reviews */}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ color: '#94A3B8', fontSize: 13, fontWeight: 600, letterSpacing: '0.5px', margin: 0 }}>
              🧠 PENDING AI REVIEWS
            </h3>
            <button onClick={() => navigate('/ai-insights')}
              style={{ background: 'none', border: 'none', color: '#0EA5E9', fontSize: 12, cursor: 'pointer' }}>
              Review all →
            </button>
          </div>
          {reviews.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{ fontSize: 32 }}>✅</div>
              <p style={{ color: '#4ADE80', fontSize: 13, margin: '8px 0 0' }}>All AI predictions reviewed</p>
            </div>
          ) : (
            reviews.slice(0, 5).map(r => (
              <div key={r.id}
                style={{ padding: '10px 0', borderBottom: '1px solid #0EA5E910' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ color: '#CBD5E1', fontSize: 13 }}>Patient #{r.patient_id}</div>
                  <span style={{
                    padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                    background: RISK_COLORS[r.risk_level] + '25',
                    color: RISK_COLORS[r.risk_level],
                  }}>{r.risk_level?.toUpperCase()}</span>
                </div>
                <div style={{ color: '#475569', fontSize: 11, marginTop: 3 }}>
                  Score: {(r.risk_score * 100).toFixed(0)}% · Confidence: {(r.confidence_score * 100).toFixed(0)}%
                </div>
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}
