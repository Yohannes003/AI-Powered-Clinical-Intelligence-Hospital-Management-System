import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { patientAPI } from '../api/client';
import toast from 'react-hot-toast';

const STATUS_OPTIONS = ['active', 'icu', 'emergency', 'discharged'];

const STATUS_COLORS = {
  active: { bg: '#22C55E20', color: '#4ADE80' },
  icu: { bg: '#DC262620', color: '#F87171' },
  emergency: { bg: '#F9731620', color: '#FB923C' },
  discharged: { bg: '#64748B20', color: '#94A3B8' },
};

const Modal = ({ open, onClose, children }) => {
  if (!open) return null;
  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000000A0', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: '#0B1E3D', border: '1px solid #0EA5E930', borderRadius: 20, padding: 32, width: 560, maxHeight: '85vh', overflow: 'auto' }}>
        {children}
      </div>
    </div>
  );
};

const Input = ({ label, value, onChange, type = 'text', required, placeholder }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ color: '#94A3B8', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 5, letterSpacing: '0.5px' }}>
      {label.toUpperCase()}{required && ' *'}
    </label>
    <input type={type} value={value} onChange={e => onChange(e.target.value)}
      required={required} placeholder={placeholder}
      style={{
        width: '100%', padding: '10px 12px', borderRadius: 8,
        background: '#060E1A', border: '1px solid #0EA5E925',
        color: '#F1F5F9', fontSize: 13, outline: 'none', boxSizing: 'border-box',
      }}
      onFocus={e => e.target.style.borderColor = '#0EA5E9'}
      onBlur={e => e.target.style.borderColor = '#0EA5E925'}
    />
  </div>
);

export default function PatientListPage() {
    const ICU_URL = process.env.REACT_APP_ICU_URL || 'http://localhost:5174';
    const [patients, setPatients] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(null);
  const navigate = useNavigate();

  const [form, setForm] = useState({
    full_name: '', date_of_birth: '', gender: 'Male',
    blood_type: '', contact_phone: '', ward: '', bed_number: '', status: 'active',
    allergies: '', chronic_conditions: '', current_medications: '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await patientAPI.list({ search: search || undefined, status: statusFilter || undefined, limit: 20 });
      setPatients(res.data.patients || []);
      setTotal(res.data.total || 0);
    } catch (e) { toast.error('Failed to load patients'); }
    finally { setLoading(false); }
  }, [search, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleStatusChange = async (patientId, newStatus, patientName) => {
    setUpdatingStatus(patientId);
    try {
      const res = await patientAPI.update(patientId, { status: newStatus });
      toast.success(`${patientName} status changed to ${newStatus}`);
      if (newStatus === 'discharged') {
        navigate(`/reports?patientId=${patientId}&name=${encodeURIComponent(patientName)}`);
      } else if (newStatus === 'icu') {
        toast.success(`${patientName} added to ICU monitoring system`, { duration: 4000 });
        load();
      } else {
        load();
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update status');
    } finally {
      setUpdatingStatus(null);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      const payload = {
        ...form,
        date_of_birth: new Date(form.date_of_birth).toISOString(),
        allergies: form.allergies ? form.allergies.split(',').map(s => s.trim()) : [],
        chronic_conditions: form.chronic_conditions ? form.chronic_conditions.split(',').map(s => s.trim()) : [],
        current_medications: form.current_medications ? form.current_medications.split(',').map(s => s.trim()) : [],
      };
      const res = await patientAPI.create(payload);
      toast.success(`Patient ${form.full_name} registered`);
      setShowCreate(false);
      setForm({ full_name: '', date_of_birth: '', gender: 'Male', blood_type: '', contact_phone: '', ward: '', bed_number: '', status: 'active', allergies: '', chronic_conditions: '', current_medications: '' });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create patient'); }
    finally { setCreating(false); }
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ color: '#F1F5F9', fontSize: 26, fontWeight: 700, margin: 0 }}>Patients</h1>
          <p style={{ color: '#475569', fontSize: 13, margin: '4px 0 0' }}>{total} total patients registered</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          style={{
            padding: '10px 20px', borderRadius: 10,
            background: 'linear-gradient(135deg, #0EA5E9, #6366F1)',
            color: '#fff', fontWeight: 700, fontSize: 14,
            border: 'none', cursor: 'pointer',
          }}>+ New Patient</button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="🔍  Search by name or MRN..."
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 10,
            background: '#0B1E3D', border: '1px solid #0EA5E920',
            color: '#F1F5F9', fontSize: 13, outline: 'none',
          }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          style={{
            padding: '10px 14px', borderRadius: 10,
            background: '#0B1E3D', border: '1px solid #0EA5E920',
            color: '#94A3B8', fontSize: 13, outline: 'none',
          }}>
          <option value="">All Statuses</option>
          {['active', 'icu', 'emergency', 'discharged'].map(s => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{ background: 'linear-gradient(135deg, #0B1E3D, #071428)', border: '1px solid #0EA5E920', borderRadius: 16, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #0EA5E920' }}>
              {['Patient', 'MRN', 'DOB', 'Ward/Bed', 'Status', 'Actions'].map(h => (
                <th key={h} style={{ padding: '14px 16px', color: '#64748B', fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', textAlign: 'left' }}>
                  {h.toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: '#475569' }}>Loading...</td></tr>
            ) : patients.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: '#475569' }}>
                No patients found. <button onClick={() => setShowCreate(true)} style={{ background: 'none', border: 'none', color: '#0EA5E9', cursor: 'pointer' }}>Add first patient →</button>
              </td></tr>
            ) : patients.map((p, i) => {
              const statusStyle = STATUS_COLORS[p.status] || STATUS_COLORS.active;
              return (
                <tr key={p.id} style={{ borderBottom: '1px solid #0EA5E908', transition: 'background 0.15s', cursor: 'pointer' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#0EA5E908'}
                  onMouseLeave={e => e.currentTarget.style.background = 'none'}
                  onClick={() => {
                    if (p.status?.toLowerCase() === 'icu') {
                      const icuDbId = (p.patient_id || String(p.id)).replace(/^.*?(\d+)$/, '$1');
                      window.open(`${ICU_URL}/?patient_id=${icuDbId}`, '_blank');
                    } else {
                      navigate(`/patients/${p.id}`);
                    }
                  }}>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #0EA5E925, #6366F125)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
                        {p.gender === 'Female' ? '👩' : '👨'}
                      </div>
                      <div>
                        <div style={{ color: '#CBD5E1', fontWeight: 600, fontSize: 13 }}>{p.full_name}</div>
                        <div style={{ color: '#475569', fontSize: 11 }}>{p.gender} · {p.blood_type || 'Unknown type'}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#64748B', fontSize: 12, fontFamily: 'monospace' }}>{p.patient_id}</td>
                  <td style={{ padding: '14px 16px', color: '#64748B', fontSize: 12 }}>
                    {p.date_of_birth ? new Date(p.date_of_birth).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '14px 16px', color: '#64748B', fontSize: 12 }}>
                    {p.ward ? `${p.ward} · Bed ${p.bed_number || '—'}` : '—'}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <select value={p.status || 'active'} onClick={e => e.stopPropagation()} onChange={e => { e.stopPropagation(); handleStatusChange(p.id, e.target.value, p.full_name); }}
                      disabled={updatingStatus === p.id}
                      style={{
                        padding: '4px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer', outline: 'none',
                        background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.color}40`,
                      }}>
                      {STATUS_OPTIONS.map(s => (
                        <option key={s} value={s} style={{ background: '#0B1E3D', color: STATUS_COLORS[s].color }}>
                          {s.charAt(0).toUpperCase() + s.slice(1)}
                        </option>
                      ))}
                    </select>
                    {updatingStatus === p.id && <span style={{ marginLeft: 4, color: '#64748B', fontSize: 10 }}>...</span>}
                  </td>
                  <td style={{ padding: '14px 16px' }} onClick={e => e.stopPropagation()}>
                    <button onClick={() => {
                        navigate(`/patients/${p.id}`);
                      }}
                      style={{ padding: '5px 12px', borderRadius: 7, background: '#0EA5E920', color: '#38BDF8', border: '1px solid #0EA5E930', cursor: 'pointer', fontSize: 12 }}>
                      View
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Create Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)}>
        <h2 style={{ color: '#F1F5F9', fontSize: 20, fontWeight: 700, margin: '0 0 20px' }}>Register New Patient</h2>
        <form onSubmit={handleCreate}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <Input label="Full Name" value={form.full_name} onChange={v => setForm(f => ({ ...f, full_name: v }))} required />
            </div>
            <Input label="Date of Birth" value={form.date_of_birth} onChange={v => setForm(f => ({ ...f, date_of_birth: v }))} type="date" required />
            <div style={{ marginBottom: 14 }}>
              <label style={{ color: '#94A3B8', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 5, letterSpacing: '0.5px' }}>GENDER *</label>
              <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, background: '#060E1A', border: '1px solid #0EA5E925', color: '#F1F5F9', fontSize: 13, outline: 'none' }}>
                {['Male', 'Female', 'Other'].map(g => <option key={g}>{g}</option>)}
              </select>
            </div>
            <Input label="Blood Type" value={form.blood_type} onChange={v => setForm(f => ({ ...f, blood_type: v }))} placeholder="A+, O-, etc." />
            <Input label="Contact Phone" value={form.contact_phone} onChange={v => setForm(f => ({ ...f, contact_phone: v }))} />
            <Input label="Ward" value={form.ward} onChange={v => setForm(f => ({ ...f, ward: v }))} placeholder="Cardiology, ICU..." />
            <Input label="Bed Number" value={form.bed_number} onChange={v => setForm(f => ({ ...f, bed_number: v }))} />
            <Input label="Status" value={form.status} onChange={v => setForm(f => ({ ...f, status: v }))} />
            <div style={{ gridColumn: '1 / -1' }}>
              <Input label="Allergies (comma-separated)" value={form.allergies} onChange={v => setForm(f => ({ ...f, allergies: v }))} placeholder="Penicillin, Aspirin..." />
              <Input label="Chronic Conditions (comma-separated)" value={form.chronic_conditions} onChange={v => setForm(f => ({ ...f, chronic_conditions: v }))} placeholder="Diabetes, Hypertension..." />
              <Input label="Current Medications (comma-separated)" value={form.current_medications} onChange={v => setForm(f => ({ ...f, current_medications: v }))} placeholder="Metformin, Lisinopril..." />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button type="button" onClick={() => setShowCreate(false)}
              style={{ flex: 1, padding: '11px', borderRadius: 10, background: '#1E3A5F', color: '#94A3B8', border: 'none', cursor: 'pointer', fontSize: 14 }}>
              Cancel
            </button>
            <button type="submit" disabled={creating}
              style={{ flex: 2, padding: '11px', borderRadius: 10, background: 'linear-gradient(135deg, #0EA5E9, #6366F1)', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer', fontSize: 14 }}>
              {creating ? 'Registering...' : 'Register Patient'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
