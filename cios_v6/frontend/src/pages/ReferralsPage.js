import React, { useState, useEffect, useCallback } from 'react';
import { referralAPI, patientAPI } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

const PRIORITY_COLOR = { routine:'#22C55E', urgent:'#F97316', stat:'#DC2626' };
const PRIORITY_BG    = { routine:'#22C55E18', urgent:'#F9731618', stat:'#DC262618' };
const STATUS_COLOR   = { pending:'#EAB308', accepted:'#22C55E', declined:'#DC2626', completed:'#6366F1', cancelled:'#64748B' };
const STATUS_BG      = { pending:'#EAB30818', accepted:'#22C55E18', declined:'#DC262618', completed:'#6366F118', cancelled:'#64748B18' };

/* ─── helpers ─────────────────────────────────────────── */
const Badge = ({ label, color, bg }) => (
  <span style={{ padding:'2px 9px', borderRadius:20, fontSize:10, fontWeight:700,
    letterSpacing:'0.4px', background: bg||`${color}20`, color,
    border:`1px solid ${color}30`, fontFamily:'monospace' }}>
    {label?.toUpperCase()}
  </span>
);

const SectionTitle = ({ children }) => (
  <div style={{ color:'#64748B', fontSize:10, fontWeight:700, letterSpacing:'0.6px',
    marginBottom:12, paddingBottom:8, borderBottom:'1px solid #0EA5E915' }}>
    {children}
  </div>
);

const Input = ({ label, value, onChange, type='text', placeholder, required, as='input', rows=3 }) => {
  const s = { width:'100%', padding:'9px 12px', borderRadius:9, background:'#060E1A',
    border:'1px solid #0EA5E920', color:'#F1F5F9', fontSize:13, outline:'none',
    boxSizing:'border-box', fontFamily:'inherit', resize:'vertical' };
  return (
    <div style={{ marginBottom:12 }}>
      <label style={{ color:'#64748B', fontSize:10, fontWeight:700, display:'block',
        marginBottom:5, letterSpacing:'0.5px' }}>
        {label}{required && ' *'}
      </label>
      {as === 'textarea'
        ? <textarea value={value} onChange={e=>onChange(e.target.value)} rows={rows}
            placeholder={placeholder} style={s}/>
        : <input type={type} value={value} onChange={e=>onChange(e.target.value)}
            placeholder={placeholder} required={required} style={s}/>}
    </div>
  );
};

/* ─── Create Referral Modal ───────────────────────────── */
function CreateReferralModal({ patients, specialties, onClose, onCreated }) {
  const [patientId,    setPatientId]    = useState('');
  const [specialty,    setSpecialty]    = useState('');
  const [reason,       setReason]       = useState('');
  const [priority,     setPriority]     = useState('routine');
  const [summary,      setSummary]      = useState('');
  const [notes,        setNotes]        = useState('');
  const [includeAI,    setIncludeAI]    = useState(true);
  const [sending,      setSending]      = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!patientId) return toast.error('Select a patient');
    if (!specialty) return toast.error('Select a specialty');
    if (!reason.trim()) return toast.error('Reason is required');
    setSending(true);
    try {
      const res = await referralAPI.create({
        patient_id: parseInt(patientId),
        specialty_requested: specialty,
        reason, priority,
        clinical_summary: summary || null,
        notes_from_referring: notes || null,
        include_ai_snapshot: includeAI,
      });
      toast.success(`✅ Referral ${res.data.referral_number} created`);
      onCreated();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create referral'); }
    finally { setSending(false); }
  };

  const overlay = { position:'fixed', inset:0, background:'#000000C0', zIndex:200,
    display:'flex', alignItems:'center', justifyContent:'center' };
  const box = { width:580, maxHeight:'88vh', overflow:'auto',
    background:'linear-gradient(135deg,#0B1E3D,#071428)',
    border:'1px solid #0EA5E930', borderRadius:18, padding:28 };

  return (
    <div style={overlay} onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={box}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:20 }}>
          <h3 style={{ color:'#F1F5F9', fontSize:17, fontWeight:700, margin:0 }}>
            📋 Create Referral
          </h3>
          <button onClick={onClose} style={{ background:'none', border:'none',
            color:'#64748B', fontSize:20, cursor:'pointer' }}>×</button>
        </div>

        <form onSubmit={submit}>
          {/* Patient */}
          <div style={{ marginBottom:12 }}>
            <label style={{ color:'#64748B', fontSize:10, fontWeight:700, display:'block', marginBottom:5 }}>
              PATIENT *
            </label>
            <select value={patientId} onChange={e=>setPatientId(e.target.value)} required
              style={{ width:'100%', padding:'9px 12px', borderRadius:9, background:'#060E1A',
                border:'1px solid #0EA5E920', color: patientId?'#F1F5F9':'#475569',
                fontSize:13, outline:'none' }}>
              <option value="">Select patient...</option>
              {patients.map(p=><option key={p.id} value={p.id}>{p.full_name} ({p.patient_id})</option>)}
            </select>
          </div>

          {/* Specialty */}
          <div style={{ marginBottom:12 }}>
            <label style={{ color:'#64748B', fontSize:10, fontWeight:700, display:'block', marginBottom:5 }}>
              SPECIALTY REQUESTED *
            </label>
            <select value={specialty} onChange={e=>setSpecialty(e.target.value)} required
              style={{ width:'100%', padding:'9px 12px', borderRadius:9, background:'#060E1A',
                border:'1px solid #0EA5E920', color: specialty?'#F1F5F9':'#475569',
                fontSize:13, outline:'none' }}>
              <option value="">Select specialty...</option>
              {specialties.map(s=><option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {/* Priority */}
          <div style={{ marginBottom:14 }}>
            <label style={{ color:'#64748B', fontSize:10, fontWeight:700, display:'block', marginBottom:6 }}>
              PRIORITY *
            </label>
            <div style={{ display:'flex', gap:8 }}>
              {['routine','urgent','stat'].map(p=>(
                <button key={p} type="button" onClick={()=>setPriority(p)}
                  style={{ flex:1, padding:'9px 0', borderRadius:9, cursor:'pointer',
                    fontSize:12, fontFamily:'inherit', fontWeight: priority===p ? 700:400,
                    border:`2px solid ${priority===p ? PRIORITY_COLOR[p] : '#0EA5E920'}`,
                    background: priority===p ? PRIORITY_BG[p] : 'transparent',
                    color: priority===p ? PRIORITY_COLOR[p] : '#64748B' }}>
                  {p==='routine' ? '🟢' : p==='urgent' ? '🟠' : '🔴'} {p.toUpperCase()}
                </button>
              ))}
            </div>
            {priority==='stat' && (
              <div style={{ marginTop:8, padding:'7px 12px', background:'#DC262612',
                border:'1px solid #DC262630', borderRadius:8, color:'#F87171', fontSize:11 }}>
                ⚠️ STAT referral — immediate specialist attention required
              </div>
            )}
          </div>

          <Input label="Reason for Referral" value={reason} onChange={setReason}
            as="textarea" rows={3} required
            placeholder="Briefly describe the clinical reason for this referral..."/>

          <Input label="Clinical Summary" value={summary} onChange={setSummary}
            as="textarea" rows={3}
            placeholder="Current diagnosis, relevant history, investigations done..."/>

          <Input label="Notes to Specialist" value={notes} onChange={setNotes}
            as="textarea" rows={2}
            placeholder="Any specific questions or requests for the specialist..."/>

          {/* AI snapshot */}
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:18,
            padding:'10px 12px', background:'#6366F108', border:'1px solid #6366F120', borderRadius:9 }}>
            <input type="checkbox" id="ai-snap" checked={includeAI}
              onChange={e=>setIncludeAI(e.target.checked)}
              style={{ width:15, height:15, cursor:'pointer' }}/>
            <label htmlFor="ai-snap" style={{ color:'#A5B4FC', fontSize:12, cursor:'pointer' }}>
              🧠 Attach current AI risk snapshot to this referral
            </label>
          </div>

          <div style={{ display:'flex', gap:10 }}>
            <button type="button" onClick={onClose}
              style={{ flex:1, padding:11, borderRadius:10, background:'#1E3A5F',
                color:'#94A3B8', border:'none', cursor:'pointer', fontSize:13 }}>Cancel</button>
            <button type="submit" disabled={sending}
              style={{ flex:2, padding:11, borderRadius:10, fontWeight:700, fontSize:13,
                border:'none', cursor: sending?'not-allowed':'pointer',
                background: sending ? '#1E3A5F':'linear-gradient(135deg,#0EA5E9,#6366F1)',
                color:'#fff' }}>
              {sending ? '⏳ Sending...' : '📋 Create Referral'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Add Consultation Note Modal ─────────────────────── */
function NoteModal({ referralId, onClose, onAdded }) {
  const [body,       setBody]       = useState('');
  const [noteType,   setNoteType]   = useState('consultation');
  const [title,      setTitle]      = useState('');
  const [findings,   setFindings]   = useState('');
  const [plan,       setPlan]       = useState('');
  const [meds,       setMeds]       = useState('');
  const [followUp,   setFollowUp]   = useState('');
  const [saving,     setSaving]     = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (!body.trim()) return toast.error('Note body is required');
    setSaving(true);
    try {
      await referralAPI.addNote(referralId, {
        body, note_type: noteType,
        title: title || null,
        findings: findings || null,
        plan: plan || null,
        medications: meds ? meds.split(',').map(s=>s.trim()).filter(Boolean) : [],
        follow_up_in: followUp || null,
      });
      toast.success('Consultation note added');
      onAdded();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to add note'); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ position:'fixed', inset:0, background:'#000000C0', zIndex:200,
      display:'flex', alignItems:'center', justifyContent:'center' }}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ width:540, maxHeight:'85vh', overflow:'auto',
        background:'linear-gradient(135deg,#0B1E3D,#071428)',
        border:'1px solid #0EA5E930', borderRadius:18, padding:26 }}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:18 }}>
          <h3 style={{ color:'#F1F5F9', fontSize:16, fontWeight:700, margin:0 }}>📝 Add Consultation Note</h3>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'#64748B', fontSize:20, cursor:'pointer' }}>×</button>
        </div>

        <form onSubmit={save}>
          {/* Note type */}
          <div style={{ marginBottom:14 }}>
            <label style={{ color:'#64748B', fontSize:10, fontWeight:700, display:'block', marginBottom:6 }}>NOTE TYPE</label>
            <div style={{ display:'flex', gap:8 }}>
              {['consultation','follow_up','discharge'].map(t=>(
                <button key={t} type="button" onClick={()=>setNoteType(t)}
                  style={{ flex:1, padding:'7px 0', borderRadius:8, cursor:'pointer',
                    fontSize:11, fontFamily:'inherit', fontWeight:noteType===t?700:400,
                    border:`2px solid ${noteType===t?'#0EA5E9':'#0EA5E920'}`,
                    background:noteType===t?'#0EA5E918':'transparent',
                    color:noteType===t?'#38BDF8':'#64748B' }}>
                  {t==='consultation'?'🩺':t==='follow_up'?'🔄':'🏥'} {t.replace('_',' ')}
                </button>
              ))}
            </div>
          </div>

          <Input label="Title" value={title} onChange={setTitle} placeholder="Cardiology Consultation Note..."/>
          <Input label="Note *" value={body} onChange={setBody} as="textarea" rows={4} required
            placeholder="Clinical assessment and consultation findings..."/>
          <Input label="Findings" value={findings} onChange={setFindings} as="textarea" rows={2}
            placeholder="Physical examination, investigation findings..."/>
          <Input label="Management Plan" value={plan} onChange={setPlan} as="textarea" rows={2}
            placeholder="Recommended treatment, interventions..."/>
          <Input label="Medications Recommended (comma-separated)" value={meds} onChange={setMeds}
            placeholder="Aspirin 75mg OD, Atorvastatin 40mg ON..."/>
          <Input label="Follow-up In" value={followUp} onChange={setFollowUp}
            placeholder="2 weeks, 1 month, 3 months..."/>

          <div style={{ display:'flex', gap:10, marginTop:4 }}>
            <button type="button" onClick={onClose}
              style={{ flex:1, padding:10, borderRadius:9, background:'#1E3A5F', color:'#94A3B8', border:'none', cursor:'pointer', fontSize:13 }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              style={{ flex:2, padding:10, borderRadius:9, fontWeight:700, fontSize:13, border:'none',
                cursor:saving?'not-allowed':'pointer',
                background:saving?'#1E3A5F':'linear-gradient(135deg,#22C55E,#16A34A)', color:'#fff' }}>
              {saving ? 'Saving...' : '📝 Save Note'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Referral Detail Panel ───────────────────────────── */
function ReferralDetail({ referral, currentUser, onBack, onRefresh }) {
  const [noteModal, setNoteModal] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [declineReason, setDeclineReason] = useState('');
  const [acting, setActing] = useState(false);

  const isReferring  = referral.referring_doctor_id === currentUser?.id;
  const isSpecialist = referral.specialist_id === currentUser?.id || !referral.specialist_id;

  const handleAccept = async () => {
    setActing(true);
    try {
      await referralAPI.accept(referral.id);
      toast.success('Referral accepted');
      onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActing(false); }
  };

  const handleDecline = async () => {
    if (!declineReason.trim()) return toast.error('Enter a reason for declining');
    setActing(true);
    try {
      await referralAPI.decline(referral.id, declineReason);
      toast.success('Referral declined');
      setDeclining(false);
      onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActing(false); }
  };

  const handleComplete = async () => {
    setActing(true);
    try {
      await referralAPI.complete(referral.id);
      toast.success('Referral marked as completed');
      onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setActing(false); }
  };

  const ai = referral.ai_risk_snapshot;

  return (
    <div>
      <button onClick={onBack} style={{ background:'none', border:'none', color:'#0EA5E9',
        cursor:'pointer', fontSize:13, marginBottom:16, padding:0 }}>← Back to referrals</button>

      {/* Header */}
      <div style={{ padding:20, background:'linear-gradient(135deg,#0B1E3D,#071428)',
        border:'1px solid #0EA5E920', borderRadius:16, marginBottom:16 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
          <div>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:6 }}>
              <span style={{ color:'#94A3B8', fontSize:12, fontFamily:'monospace' }}>
                {referral.referral_number}
              </span>
              <Badge label={referral.priority} color={PRIORITY_COLOR[referral.priority]}
                bg={PRIORITY_BG[referral.priority]}/>
              <Badge label={referral.status} color={STATUS_COLOR[referral.status]}
                bg={STATUS_BG[referral.status]}/>
            </div>
            <h2 style={{ color:'#F1F5F9', fontSize:20, fontWeight:700, margin:'0 0 4px' }}>
              {referral.specialty_requested}
            </h2>
            <div style={{ color:'#64748B', fontSize:12 }}>
              Patient: <span style={{ color:'#CBD5E1' }}>{referral.patient_name || `#${referral.patient_id}`}</span>
              {' · '}From: <span style={{ color:'#CBD5E1' }}>{referral.referring_doctor_name || `Dr. #${referral.referring_doctor_id}`}</span>
              {referral.specialist_name && <>{' · '}Specialist: <span style={{ color:'#CBD5E1' }}>{referral.specialist_name}</span></>}
              {' · '}<span style={{ color:'#475569' }}>{referral.created_at ? new Date(referral.created_at).toLocaleString() : ''}</span>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
            {referral.status === 'pending' && !isReferring && (
              <>
                <button onClick={handleAccept} disabled={acting}
                  style={{ padding:'8px 16px', borderRadius:9, background:'#22C55E', color:'#fff',
                    fontWeight:700, fontSize:12, border:'none', cursor:'pointer' }}>
                  ✅ Accept
                </button>
                <button onClick={() => setDeclining(true)}
                  style={{ padding:'8px 16px', borderRadius:9, background:'#DC262618', color:'#F87171',
                    fontWeight:700, fontSize:12, border:'1px solid #DC262630', cursor:'pointer' }}>
                  ❌ Decline
                </button>
              </>
            )}
            {referral.status === 'accepted' && (
              <>
                <button onClick={() => setNoteModal(true)}
                  style={{ padding:'8px 16px', borderRadius:9,
                    background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
                    fontWeight:700, fontSize:12, border:'none', cursor:'pointer' }}>
                  📝 Add Note
                </button>
                <button onClick={handleComplete} disabled={acting}
                  style={{ padding:'8px 16px', borderRadius:9, background:'#6366F118', color:'#A5B4FC',
                    fontWeight:700, fontSize:12, border:'1px solid #6366F130', cursor:'pointer' }}>
                  ✓ Complete
                </button>
              </>
            )}
            {referral.status === 'completed' && (
              <button onClick={() => setNoteModal(true)}
                style={{ padding:'8px 16px', borderRadius:9,
                  background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
                  fontWeight:700, fontSize:12, border:'none', cursor:'pointer' }}>
                📝 Add Follow-up Note
              </button>
            )}
          </div>
        </div>

        {/* Decline form inline */}
        {declining && (
          <div style={{ marginTop:14, padding:14, background:'#DC262608',
            border:'1px solid #DC262625', borderRadius:10 }}>
            <label style={{ color:'#F87171', fontSize:10, fontWeight:700,
              display:'block', marginBottom:6 }}>REASON FOR DECLINING *</label>
            <textarea value={declineReason} onChange={e=>setDeclineReason(e.target.value)} rows={2}
              placeholder="E.g. Capacity issues, not within scope..."
              style={{ width:'100%', padding:'8px 10px', borderRadius:8, background:'#0B1E3D',
                border:'1px solid #DC262630', color:'#F1F5F9', fontSize:12, outline:'none',
                resize:'vertical', boxSizing:'border-box', fontFamily:'inherit' }}/>
            <div style={{ display:'flex', gap:8, marginTop:8 }}>
              <button onClick={handleDecline} disabled={acting}
                style={{ padding:'7px 16px', borderRadius:8, background:'#DC2626',
                  color:'#fff', fontWeight:700, fontSize:12, border:'none', cursor:'pointer' }}>
                Confirm Decline
              </button>
              <button onClick={() => setDeclining(false)}
                style={{ padding:'7px 14px', borderRadius:8, background:'#1E3A5F',
                  color:'#94A3B8', border:'none', cursor:'pointer', fontSize:12 }}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16 }}>
        {/* Clinical info */}
        <div style={{ padding:18, background:'linear-gradient(135deg,#0B1E3D,#071428)',
          border:'1px solid #0EA5E920', borderRadius:14 }}>
          <SectionTitle>CLINICAL INFORMATION</SectionTitle>
          <div style={{ marginBottom:12 }}>
            <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:4 }}>REASON FOR REFERRAL</div>
            <div style={{ color:'#CBD5E1', fontSize:13, lineHeight:1.7 }}>{referral.reason}</div>
          </div>
          {referral.clinical_summary && (
            <div style={{ marginBottom:12 }}>
              <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:4 }}>CLINICAL SUMMARY</div>
              <div style={{ color:'#94A3B8', fontSize:12, lineHeight:1.7 }}>{referral.clinical_summary}</div>
            </div>
          )}
          {referral.notes_from_referring && (
            <div style={{ marginBottom:12 }}>
              <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:4 }}>NOTES FROM REFERRING DR.</div>
              <div style={{ color:'#94A3B8', fontSize:12, lineHeight:1.7 }}>{referral.notes_from_referring}</div>
            </div>
          )}
          {referral.notes_from_specialist && (
            <div>
              <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:4 }}>SPECIALIST NOTES</div>
              <div style={{ color:'#94A3B8', fontSize:12, lineHeight:1.7 }}>{referral.notes_from_specialist}</div>
            </div>
          )}
        </div>

        {/* AI Risk Snapshot */}
        <div style={{ padding:18, background:'linear-gradient(135deg,#0B1E3D,#071428)',
          border:'1px solid #0EA5E920', borderRadius:14 }}>
          <SectionTitle>🧠 AI RISK SNAPSHOT AT REFERRAL</SectionTitle>
          {ai ? (
            <>
              <div style={{ display:'flex', gap:12, alignItems:'center', marginBottom:14 }}>
                <div style={{ padding:'12px 16px', borderRadius:12,
                  background: `${STATUS_COLOR[ai.risk_level]||'#0EA5E9'}18`,
                  border:`1px solid ${STATUS_COLOR[ai.risk_level]||'#0EA5E9'}30`,
                  textAlign:'center', flexShrink:0 }}>
                  <div style={{ color: STATUS_COLOR[ai.risk_level]||'#0EA5E9',
                    fontSize:24, fontWeight:800, fontFamily:'monospace' }}>
                    {Math.round((ai.risk_score||0)*100)}%
                  </div>
                  <div style={{ color: STATUS_COLOR[ai.risk_level]||'#0EA5E9', fontSize:10, fontWeight:700 }}>
                    {ai.risk_level?.toUpperCase()}
                  </div>
                </div>
                <div>
                  <div style={{ color:'#64748B', fontSize:10, marginBottom:4 }}>
                    Captured: {ai.snapshot_time ? new Date(ai.snapshot_time).toLocaleString() : '—'}
                  </div>
                  <div style={{ color:'#64748B', fontSize:10 }}>
                    Confidence: {Math.round((ai.confidence||0)*100)}%
                  </div>
                </div>
              </div>
              {(ai.explanation||[]).map((e,i) => (
                <div key={i} style={{ padding:'5px 10px', marginBottom:5,
                  background:'#F9731608', border:'1px solid #F9731625',
                  borderRadius:7, color:'#CBD5E1', fontSize:11 }}>⚡ {e}</div>
              ))}
            </>
          ) : (
            <div style={{ color:'#475569', fontSize:13, textAlign:'center', padding:'20px 0' }}>
              No AI snapshot attached to this referral
            </div>
          )}
        </div>
      </div>

      {/* Consultation Notes */}
      <div style={{ padding:18, background:'linear-gradient(135deg,#0B1E3D,#071428)',
        border:'1px solid #0EA5E920', borderRadius:14 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
          <SectionTitle>📝 CONSULTATION NOTES ({referral.consultation_notes?.length || 0})</SectionTitle>
          {(referral.status === 'accepted' || referral.status === 'completed') && (
            <button onClick={() => setNoteModal(true)}
              style={{ padding:'5px 12px', borderRadius:8, fontSize:11, fontWeight:700,
                background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
                border:'none', cursor:'pointer' }}>
              + Add Note
            </button>
          )}
        </div>

        {!referral.consultation_notes?.length ? (
          <div style={{ textAlign:'center', padding:'24px 0', color:'#475569', fontSize:13 }}>
            No consultation notes yet.
            {referral.status === 'pending' && ' Accept the referral to add notes.'}
          </div>
        ) : referral.consultation_notes.map(note => (
          <div key={note.id} style={{ padding:16, marginBottom:12, background:'#060E1A',
            border:'1px solid #0EA5E915', borderRadius:12 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
              <div>
                <span style={{ color:'#CBD5E1', fontWeight:700, fontSize:13 }}>{note.title}</span>
                <span style={{ marginLeft:10 }}>
                  <Badge label={note.note_type.replace('_',' ')} color="#6366F1" bg="#6366F118"/>
                </span>
              </div>
              <div style={{ color:'#334155', fontSize:10, textAlign:'right' }}>
                <div>{note.author_name}</div>
                <div>{note.created_at ? new Date(note.created_at).toLocaleString() : ''}</div>
              </div>
            </div>

            <p style={{ color:'#94A3B8', fontSize:13, lineHeight:1.7, margin:'0 0 10px' }}>{note.body}</p>

            {note.findings && (
              <div style={{ marginBottom:8 }}>
                <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:3 }}>FINDINGS</div>
                <div style={{ color:'#94A3B8', fontSize:12, lineHeight:1.6 }}>{note.findings}</div>
              </div>
            )}
            {note.plan && (
              <div style={{ marginBottom:8 }}>
                <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:3 }}>MANAGEMENT PLAN</div>
                <div style={{ color:'#94A3B8', fontSize:12, lineHeight:1.6 }}>{note.plan}</div>
              </div>
            )}
            {note.medications?.length > 0 && (
              <div style={{ marginBottom:8 }}>
                <div style={{ color:'#475569', fontSize:10, fontWeight:700, marginBottom:5 }}>MEDICATIONS</div>
                <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
                  {note.medications.map((m,i) => (
                    <span key={i} style={{ padding:'2px 9px', background:'#22C55E18',
                      color:'#4ADE80', border:'1px solid #22C55E25', borderRadius:20, fontSize:11 }}>
                      💊 {m}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {note.follow_up_in && (
              <div style={{ marginTop:8, padding:'5px 10px', background:'#0EA5E908',
                border:'1px solid #0EA5E920', borderRadius:7, color:'#38BDF8', fontSize:11 }}>
                🔄 Follow-up in: {note.follow_up_in}
              </div>
            )}
          </div>
        ))}
      </div>

      {noteModal && (
        <NoteModal referralId={referral.id} onClose={() => setNoteModal(false)}
          onAdded={() => { setNoteModal(false); onRefresh(); }}/>
      )}
    </div>
  );
}

/* ─── Main ReferralsPage ──────────────────────────────── */
export default function ReferralsPage() {
  const { user }                      = useAuth();
  const [referrals, setReferrals]     = useState([]);
  const [stats, setStats]             = useState(null);
  const [specialties, setSpecialties] = useState([]);
  const [patients, setPatients]       = useState([]);
  const [selected, setSelected]       = useState(null);
  const [creating, setCreating]       = useState(false);
  const [loading, setLoading]         = useState(true);
  const [roleFilter, setRoleFilter]   = useState('both');
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [refRes, statsRes] = await Promise.all([
        referralAPI.list({ role: roleFilter, status: statusFilter || undefined }),
        referralAPI.stats(),
      ]);
      setReferrals(refRes.data.referrals || []);
      setStats(statsRes.data);
    } catch (e) { toast.error('Failed to load referrals'); }
    finally { setLoading(false); }
  }, [roleFilter, statusFilter]);

  useEffect(() => {
    load();
    referralAPI.specialties().then(r => setSpecialties(r.data.specialties || [])).catch(() => {});
    patientAPI.list({ limit: 100 }).then(r => setPatients(r.data.patients || [])).catch(() => {});
  }, [load]);

  if (selected) {
    return (
      <ReferralDetail
        referral={selected}
        currentUser={user}
        onBack={() => { setSelected(null); load(); }}
        onRefresh={() => {
          // Refresh the selected referral data
          referralAPI.list({ role: 'both' }).then(r => {
            const updated = (r.data.referrals || []).find(ref => ref.id === selected.id);
            if (updated) setSelected(updated);
            setReferrals(r.data.referrals || []);
          });
        }}
      />
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', marginBottom:22 }}>
        <div>
          <h1 style={{ color:'#F1F5F9', fontSize:24, fontWeight:700, margin:0 }}>📋 Referral System</h1>
          <p style={{ color:'#475569', fontSize:13, margin:'3px 0 0' }}>
            Clinical referrals · Specialist consultations · Care coordination
          </p>
        </div>
        <button onClick={() => setCreating(true)}
          style={{ padding:'10px 22px', borderRadius:10, fontWeight:700, fontSize:13,
            background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
            border:'none', cursor:'pointer' }}>
          📋 New Referral
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14, marginBottom:20 }}>
          {[
            { label:'Sent by Me',       val:stats.sent_total,   color:'#0EA5E9' },
            { label:'Received',         val:stats.recv_total,   color:'#6366F1' },
            { label:'Awaiting Action',  val:stats.pending_recv, color:'#EAB308' },
            { label:'STAT Pending',     val:stats.stat_pending, color:'#DC2626' },
          ].map(({ label, val, color }) => (
            <div key={label} style={{ padding:'14px 18px',
              background:'linear-gradient(135deg,#0B1E3D,#071428)',
              border:`1px solid ${val>0&&color==='#DC2626'?'#DC262640':'#0EA5E920'}`,
              borderRadius:12 }}>
              <div style={{ color:'#475569', fontSize:9, fontWeight:700, letterSpacing:'0.6px', marginBottom:5 }}>
                {label.toUpperCase()}
              </div>
              <div style={{ color, fontSize:28, fontWeight:700, fontFamily:'monospace' }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <div style={{ display:'flex', background:'#0B1E3D', borderRadius:10, padding:4 }}>
          {[['both','All'],['referring','Sent by Me'],['specialist','Received']].map(([v,l]) => (
            <button key={v} onClick={() => setRoleFilter(v)}
              style={{ padding:'6px 14px', borderRadius:7, border:'none', cursor:'pointer',
                fontSize:12, fontFamily:'inherit', fontWeight:roleFilter===v?700:400,
                background:roleFilter===v?'linear-gradient(135deg,#0EA5E9,#6366F1)':'transparent',
                color:roleFilter===v?'#fff':'#64748B' }}>
              {l}
            </button>
          ))}
        </div>

        <div style={{ display:'flex', gap:6 }}>
          {['','pending','accepted','completed','declined'].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              style={{ padding:'6px 12px', borderRadius:9, cursor:'pointer', fontSize:11,
                fontFamily:'inherit', fontWeight:statusFilter===s?700:400,
                border:`1px solid ${statusFilter===s?(STATUS_COLOR[s]||'#0EA5E9'):'#0EA5E920'}`,
                background:statusFilter===s?(STATUS_BG[s]||'#0EA5E918'):'transparent',
                color:statusFilter===s?(STATUS_COLOR[s]||'#38BDF8'):'#64748B' }}>
              {s || 'ALL'}
            </button>
          ))}
        </div>
      </div>

      {/* Referral list */}
      <div style={{ background:'linear-gradient(135deg,#0B1E3D,#071428)',
        border:'1px solid #0EA5E920', borderRadius:16, overflow:'hidden' }}>
        {loading ? (
          <div style={{ padding:40, textAlign:'center', color:'#475569' }}>Loading referrals...</div>
        ) : referrals.length === 0 ? (
          <div style={{ padding:60, textAlign:'center' }}>
            <div style={{ fontSize:48, marginBottom:12 }}>📋</div>
            <p style={{ color:'#475569', fontSize:14 }}>No referrals found</p>
            <button onClick={() => setCreating(true)}
              style={{ marginTop:12, padding:'9px 20px', borderRadius:10, fontWeight:700,
                background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
                border:'none', cursor:'pointer', fontSize:13 }}>
              Create your first referral
            </button>
          </div>
        ) : referrals.map(ref => (
          <div key={ref.id} onClick={() => setSelected(ref)}
            style={{ padding:'16px 20px', borderBottom:'1px solid #0EA5E90a',
              cursor:'pointer', transition:'background .15s' }}
            onMouseEnter={e=>e.currentTarget.style.background='#0EA5E908'}
            onMouseLeave={e=>e.currentTarget.style.background='none'}>

            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:12 }}>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:5, flexWrap:'wrap' }}>
                  <span style={{ color:'#F1F5F9', fontWeight:700, fontSize:14 }}>
                    {ref.specialty_requested}
                  </span>
                  <Badge label={ref.priority} color={PRIORITY_COLOR[ref.priority]}
                    bg={PRIORITY_BG[ref.priority]}/>
                  <Badge label={ref.status} color={STATUS_COLOR[ref.status]}
                    bg={STATUS_BG[ref.status]}/>
                  <span style={{ color:'#334155', fontSize:10, fontFamily:'monospace' }}>
                    {ref.referral_number}
                  </span>
                </div>

                <div style={{ color:'#94A3B8', fontSize:12, marginBottom:4, lineHeight:1.5 }}>
                  <span style={{ color:'#CBD5E1' }}>
                    {ref.patient_name || `Patient #${ref.patient_id}`}
                  </span>
                  {' · '}
                  {ref.referring_doctor_id === user?.id
                    ? <span style={{ color:'#0EA5E9' }}>You referred →</span>
                    : <span>From: <span style={{ color:'#CBD5E1' }}>{ref.referring_doctor_name}</span></span>}
                  {ref.specialist_name && <> · Specialist: <span style={{ color:'#CBD5E1' }}>{ref.specialist_name}</span></>}
                </div>

                <div style={{ color:'#475569', fontSize:12, overflow:'hidden',
                  textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  {ref.reason}
                </div>
              </div>

              <div style={{ textAlign:'right', flexShrink:0 }}>
                <div style={{ color:'#334155', fontSize:11, marginBottom:4 }}>
                  {ref.created_at ? new Date(ref.created_at).toLocaleDateString() : ''}
                </div>
                {ref.consultation_notes?.length > 0 && (
                  <div style={{ color:'#6366F1', fontSize:10 }}>
                    📝 {ref.consultation_notes.length} note{ref.consultation_notes.length!==1?'s':''}
                  </div>
                )}
                {ref.ai_risk_snapshot && (
                  <div style={{ color:'#94A3B8', fontSize:10, marginTop:2 }}>
                    🧠 AI {Math.round((ref.ai_risk_snapshot.risk_score||0)*100)}%
                    <span style={{ color: STATUS_COLOR[ref.ai_risk_snapshot.risk_level]||'#64748B',
                      marginLeft:4, fontWeight:700 }}>
                      {ref.ai_risk_snapshot.risk_level?.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create modal */}
      {creating && (
        <CreateReferralModal
          patients={patients}
          specialties={specialties}
          onClose={() => setCreating(false)}
          onCreated={() => { setCreating(false); load(); }}
        />
      )}
    </div>
  );
}
