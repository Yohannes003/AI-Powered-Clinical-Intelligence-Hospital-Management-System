import React, { useState, useEffect, useRef } from 'react';
import { patientAPI, reportAPI } from '../api/client';
import toast from 'react-hot-toast';

export default function ReportsPage() {
  const [patients, setPatients]   = useState([]);
  const [reports, setReports]     = useState([]);
  const [generating, setGenerating] = useState(false);
  const [form, setForm]           = useState({ patient_id: '', format: 'pdf', include_ai: true });

  const loadReports = () =>
    reportAPI.list().then(r => setReports(r.data.reports || [])).catch(() => {});

  const autoGenRef = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const queryPatientId = params.get('patientId');
    const patientName = params.get('name');
    patientAPI.list({ limit: 50 }).then(r => {
      setPatients(r.data.patients || []);
      if (queryPatientId && !autoGenRef.current) {
        autoGenRef.current = true;
        setForm(f => ({ ...f, patient_id: queryPatientId }));
        // Auto-generate discharge report
        setTimeout(async () => {
          setGenerating(true);
          try {
            const res = await reportAPI.generate({
              patient_id: queryPatientId,
              format: 'pdf',
              include_ai: true,
            });
            toast.success(`✅ Discharge report ready — ${res.data.file_size_kb} KB`);
            await loadReports();
            const dlUrl = reportAPI.downloadUrl(res.data.report_db_id);
            const a = document.createElement('a');
            a.href = dlUrl;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.click();
          } catch (err) {
            toast.error(err.response?.data?.detail || 'Report generation failed');
          } finally {
            setGenerating(false);
          }
        }, 500);
      }
    }).catch(() => {});
    loadReports();
  }, []);

  const generate = async (e) => {
    e.preventDefault();
    if (!form.patient_id) return toast.error('Please select a patient');
    setGenerating(true);
    try {
      const res = await reportAPI.generate({
        patient_id: form.patient_id,
        format: form.format,
        include_ai: form.include_ai,
      });
      toast.success(`✅ ${form.format.toUpperCase()} report ready — ${res.data.file_size_kb} KB`);
      await loadReports();
      // Auto-download
      const dlUrl = reportAPI.downloadUrl(res.data.report_db_id);
      const a = document.createElement('a');
      a.href = dlUrl;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.click();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Report generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const formatIcons = { pdf: '📄', csv: '📊', excel: '📈', xlsx: '📈', xps: '🖨️' };
  const s = { // inline styles
    page:   { background:'#060E1A', minHeight:'100vh', fontFamily:'inherit' },
    title:  { color:'#F1F5F9', fontSize:26, fontWeight:700, margin:'0 0 4px' },
    sub:    { color:'#475569', fontSize:13, margin:'0 0 24px' },
    grid:   { display:'grid', gridTemplateColumns:'380px 1fr', gap:20 },
    card:   { background:'linear-gradient(135deg,#0B1E3D,#071428)', border:'1px solid #0EA5E920', borderRadius:16, padding:22 },
    label:  { color:'#64748B', fontSize:11, fontWeight:700, display:'block', marginBottom:6, letterSpacing:'0.5px' },
    select: { width:'100%', padding:'10px 12px', borderRadius:10, background:'#060E1A', border:'1px solid #0EA5E925', color:'#F1F5F9', fontSize:13, outline:'none', marginBottom:14 },
    fmtGrid:{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:14 },
    genBtn: { width:'100%', padding:12, borderRadius:10, background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff', fontWeight:700, fontSize:14, border:'none', cursor:'pointer', marginTop:4 },
    disBtn: { width:'100%', padding:12, borderRadius:10, background:'#1E3A5F', color:'#64748B', fontWeight:700, fontSize:14, border:'none', cursor:'not-allowed', marginTop:4 },
    table:  { width:'100%', borderCollapse:'collapse' },
    th:     { padding:'11px 16px', color:'#334155', fontSize:10, fontWeight:700, letterSpacing:'0.6px', textAlign:'left', borderBottom:'1px solid #0EA5E920' },
    td:     { padding:'12px 16px', borderBottom:'1px solid #ffffff05' },
    dlBtn:  { padding:'6px 14px', borderRadius:8, background:'#22C55E18', color:'#4ADE80', border:'1px solid #22C55E30', textDecoration:'none', fontSize:12, fontWeight:600, display:'inline-block' },
  };

  return (
    <div>
      <h1 style={s.title}>Reports & Exports</h1>
      <p style={s.sub}>Generate AI-powered clinical reports · PDF, CSV, Excel, XPS</p>

      <div style={s.grid}>

        {/* ── Generate form ── */}
        <div style={s.card}>
          <p style={{...s.label, marginBottom:16, fontSize:12}}>GENERATE NEW REPORT</p>
          <form onSubmit={generate}>

            <label style={s.label}>PATIENT</label>
            <select
              value={form.patient_id}
              onChange={e => setForm(f => ({ ...f, patient_id: e.target.value }))}
              required style={s.select}
            >
              <option value="">Select patient...</option>
              {patients.map(p => (
                <option key={p.id} value={p.id}>{p.full_name} ({p.patient_id})</option>
              ))}
            </select>

            <label style={s.label}>FORMAT</label>
            <div style={s.fmtGrid}>
              {['pdf', 'csv', 'excel', 'xps'].map(fmt => (
                <button key={fmt} type="button"
                  onClick={() => setForm(f => ({ ...f, format: fmt }))}
                  style={{
                    padding:10, borderRadius:10, cursor:'pointer', fontSize:14,
                    border: `2px solid ${form.format === fmt ? '#0EA5E9' : '#0EA5E920'}`,
                    background: form.format === fmt ? '#0EA5E920' : 'transparent',
                    color: form.format === fmt ? '#38BDF8' : '#64748B',
                    fontWeight: form.format === fmt ? 700 : 400,
                  }}>
                  {formatIcons[fmt]} {fmt.toUpperCase()}
                </button>
              ))}
            </div>

            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16 }}>
              <input type="checkbox" id="inc-ai" checked={form.include_ai}
                onChange={e => setForm(f => ({ ...f, include_ai: e.target.checked }))}
                style={{ width:15, height:15, cursor:'pointer' }}/>
              <label htmlFor="inc-ai" style={{ color:'#94A3B8', fontSize:13, cursor:'pointer' }}>
                🧠 Include AI analysis &amp; summary
              </label>
            </div>

            <button type="submit" disabled={generating}
              style={generating ? s.disBtn : s.genBtn}>
              {generating ? '⏳ Generating...' : `📋 Generate ${form.format.toUpperCase()}`}
            </button>
          </form>

          {/* Info box */}
          <div style={{ marginTop:16, padding:12, background:'#0EA5E908', border:'1px solid #0EA5E918', borderRadius:10 }}>
            <p style={{ color:'#475569', fontSize:11, margin:0, lineHeight:1.8 }}>
              📄 <strong style={{color:'#64748B'}}>PDF</strong> — Full formatted report with AI risk banner<br/>
              📊 <strong style={{color:'#64748B'}}>CSV</strong> — Raw data export for spreadsheets<br/>
              📈 <strong style={{color:'#64748B'}}>Excel</strong> — Multi-sheet workbook with AI analysis<br/>
              🖨️ <strong style={{color:'#64748B'}}>XPS</strong> — Print-ready document
            </p>
          </div>
        </div>

        {/* ── Reports list ── */}
        <div style={{ ...s.card, padding:0, overflow:'hidden' }}>
          <div style={{ padding:'16px 20px', borderBottom:'1px solid #0EA5E920' }}>
            <p style={{ color:'#64748B', fontSize:11, fontWeight:700, letterSpacing:'0.6px', margin:0 }}>
              GENERATED REPORTS — {reports.length} files
            </p>
          </div>

          {reports.length === 0 ? (
            <div style={{ padding:60, textAlign:'center' }}>
              <div style={{ fontSize:48, marginBottom:12 }}>📋</div>
              <p style={{ color:'#475569', fontSize:14 }}>No reports yet — generate one above</p>
            </div>
          ) : (
            <table style={s.table}>
              <thead>
                <tr>
                  {['Report Title', 'Patient', 'Format', 'Created', 'Download'].map(h => (
                    <th key={h} style={s.th}>{h.toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id}
                    onMouseEnter={e => e.currentTarget.style.background = '#0EA5E908'}
                    onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                    <td style={s.td}>
                      <div style={{ color:'#CBD5E1', fontWeight:600, fontSize:13 }}>{r.title}</div>
                      <div style={{ color:'#334155', fontSize:10, fontFamily:'monospace' }}>{r.report_id}</div>
                    </td>
                    <td style={{ ...s.td, color:'#64748B', fontSize:12 }}>
                      {r.patient_id ? `Patient #${r.patient_id}` : 'Department'}
                    </td>
                    <td style={s.td}>
                      <span style={{ padding:'2px 10px', borderRadius:20, fontSize:10, fontWeight:700, background:'#0EA5E920', color:'#38BDF8' }}>
                        {formatIcons[r.format]} {r.format?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ ...s.td, color:'#475569', fontSize:11 }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                    </td>
                    <td style={s.td}>
                      {/* Use token-based download URL — no "Not authenticated" error */}
                      <a
                        href={reportAPI.downloadUrl(r.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={s.dlBtn}
                      >
                        ⬇ Download
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  );
}
