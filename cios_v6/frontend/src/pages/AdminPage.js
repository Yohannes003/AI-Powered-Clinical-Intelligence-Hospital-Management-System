import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

const ROLES = ['doctor','nurse','lab_tech','viewer','admin'];
const ROLE_COLORS = {
  admin:'#6366F1', doctor:'#0EA5E9', nurse:'#22C55E',
  lab_tech:'#F97316', viewer:'#64748B'
};
const ROLE_BG = {
  admin:'#6366F118', doctor:'#0EA5E918', nurse:'#22C55E18',
  lab_tech:'#F9731618', viewer:'#64748B18'
};

const Card = ({ children, style = {} }) => (
  <div style={{ background:'linear-gradient(135deg,#0B1E3D,#071428)',
    border:'1px solid #0EA5E920', borderRadius:16, ...style }}>
    {children}
  </div>
);

const Badge = ({ label, color }) => (
  <span style={{ padding:'2px 10px', borderRadius:20, fontSize:10, fontWeight:700,
    background: color+'18', color, border:`1px solid ${color}30`,
    fontFamily:'monospace', letterSpacing:'0.4px' }}>
    {label?.toUpperCase()}
  </span>
);

const TabBtn = ({ label, active, onClick, badge }) => (
  <button onClick={onClick} style={{
    padding:'8px 18px', borderRadius:8, border:'none', cursor:'pointer',
    fontSize:13, fontWeight: active ? 700 : 400, position:'relative',
    background: active ? 'linear-gradient(135deg,#0EA5E9,#6366F1)' : 'transparent',
    color: active ? '#fff' : '#64748B', fontFamily:'inherit',
  }}>
    {label}
    {badge > 0 && (
      <span style={{ position:'absolute', top:2, right:4, background:'#DC2626',
        color:'#fff', borderRadius:'50%', width:16, height:16, fontSize:9,
        display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700 }}>
        {badge}
      </span>
    )}
  </button>
);

// ── Approval Desk ─────────────────────────────────────────
function ApprovalDesk({ onRefresh }) {
  const [pending, setPending]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [roleMap, setRoleMap]   = useState({});
  const [rejectId, setRejectId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await adminAPI.getPending();
      setPending(r.data.pending || []);
    } catch { toast.error('Failed to load pending approvals'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (user) => {
    const role = roleMap[user.id] || user.role;
    try {
      await adminAPI.approveUser(user.id, role, user.department);
      toast.success(`✅ ${user.full_name} approved as ${role}`);
      load(); onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Approval failed'); }
  };

  const reject = async (user) => {
    if (!rejectReason.trim()) return toast.error('Please enter a rejection reason');
    try {
      await adminAPI.rejectUser(user.id, rejectReason);
      toast.success(`❌ ${user.full_name} rejected`);
      setRejectId(null); setRejectReason('');
      load(); onRefresh();
    } catch (e) { toast.error(e.response?.data?.detail || 'Rejection failed'); }
  };

  const s = {
    label: { color:'#64748B', fontSize:10, fontWeight:700, letterSpacing:'0.5px', display:'block', marginBottom:6 },
    select: { padding:'7px 10px', borderRadius:8, background:'#060E1A',
      border:'1px solid #0EA5E920', color:'#F1F5F9', fontSize:12, outline:'none' },
    appBtn: { padding:'7px 16px', borderRadius:8, background:'linear-gradient(135deg,#22C55E,#16A34A)',
      color:'#fff', fontWeight:700, fontSize:12, border:'none', cursor:'pointer', marginRight:8 },
    rejBtn: { padding:'7px 16px', borderRadius:8, background:'#DC262618',
      color:'#F87171', fontWeight:700, fontSize:12, border:'1px solid #DC262630', cursor:'pointer' },
  };

  if (loading) return <div style={{padding:40, textAlign:'center', color:'#475569'}}>Loading...</div>;

  if (pending.length === 0) return (
    <div style={{ padding:60, textAlign:'center' }}>
      <div style={{ fontSize:48, marginBottom:12 }}>✅</div>
      <p style={{ color:'#4ADE80', fontSize:16, fontWeight:600 }}>No pending approvals</p>
      <p style={{ color:'#475569', fontSize:13 }}>All signup requests have been reviewed</p>
    </div>
  );

  return (
    <div style={{ padding:20 }}>
      {pending.map(u => (
        <div key={u.id} style={{ marginBottom:14, padding:18,
          background:'#060E1A', border:'1px solid #EAB30830', borderRadius:12 }}>

          {/* User info */}
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:14 }}>
            <div style={{ display:'flex', gap:12, alignItems:'center' }}>
              <div style={{ width:44, height:44, borderRadius:12,
                background:'linear-gradient(135deg,#0EA5E930,#6366F130)',
                display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>
                {u.role === 'nurse' ? '👩‍⚕️' : u.role === 'lab_tech' ? '🔬' : '👨‍⚕️'}
              </div>
              <div>
                <div style={{ color:'#CBD5E1', fontWeight:700, fontSize:15 }}>{u.full_name}</div>
                <div style={{ color:'#475569', fontSize:12 }}>{u.email}</div>
                <div style={{ color:'#334155', fontSize:11, marginTop:2 }}>
                  Requested: <Badge label={u.role} color={ROLE_COLORS[u.role]||'#64748B'}/>
                  {u.department && <span style={{ marginLeft:8, color:'#475569' }}>· {u.department}</span>}
                  {u.license_number && <span style={{ marginLeft:8, color:'#475569' }}>· License: {u.license_number}</span>}
                </div>
                <div style={{ color:'#334155', fontSize:10, marginTop:3 }}>
                  Applied: {u.created_at ? new Date(u.created_at).toLocaleString() : '—'}
                </div>
              </div>
            </div>
            <Badge label="PENDING" color="#EAB308"/>
          </div>

          {/* Role selector */}
          <div style={{ display:'flex', alignItems:'center', gap:14, marginBottom:12 }}>
            <div>
              <label style={s.label}>ASSIGN ROLE (override if needed)</label>
              <select value={roleMap[u.id] || u.role}
                onChange={e => setRoleMap(m => ({ ...m, [u.id]: e.target.value }))}
                style={s.select}>
                {ROLES.filter(r => r !== 'admin').map(r => (
                  <option key={r} value={r}>{r.replace('_',' ').toUpperCase()}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Permission preview */}
          <div style={{ marginBottom:12, padding:10, background:'#0EA5E908',
            border:'1px solid #0EA5E915', borderRadius:8 }}>
            <div style={{ color:'#475569', fontSize:10, marginBottom:6 }}>
              PERMISSIONS THAT WILL BE GRANTED as {(roleMap[u.id]||u.role).toUpperCase()}:
            </div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:4 }}>
              {getPreviewPerms(roleMap[u.id] || u.role).map(p => (
                <span key={p} style={{ padding:'1px 7px', background:'#22C55E10',
                  color:'#4ADE80', border:'1px solid #22C55E20', borderRadius:20, fontSize:9 }}>
                  {p}
                </span>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <button onClick={() => approve(u)} style={s.appBtn}>✅ Approve</button>
            <button onClick={() => setRejectId(rejectId === u.id ? null : u.id)} style={s.rejBtn}>
              ❌ Reject
            </button>
          </div>

          {/* Reject form */}
          {rejectId === u.id && (
            <div style={{ marginTop:12, padding:12, background:'#DC262608',
              border:'1px solid #DC262620', borderRadius:8 }}>
              <label style={{ ...s.label, color:'#F87171' }}>REJECTION REASON *</label>
              <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)}
                rows={2} placeholder="E.g. Missing license number, invalid credentials..."
                style={{ width:'100%', padding:'8px 10px', borderRadius:7, background:'#0B1E3D',
                  border:'1px solid #DC262630', color:'#F1F5F9', fontSize:12, outline:'none',
                  resize:'vertical', boxSizing:'border-box', fontFamily:'inherit', marginBottom:8 }}/>
              <button onClick={() => reject(u)}
                style={{ padding:'7px 16px', borderRadius:8, background:'#DC2626',
                  color:'#fff', fontWeight:700, fontSize:12, border:'none', cursor:'pointer' }}>
                Confirm Rejection
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function getPreviewPerms(role) {
  const perms = {
    doctor: ['patient:view','patient:create','vitals:record','diagnosis:add','ai:assess','report:generate','lab:order'],
    nurse:  ['patient:view','vitals:record','alert:acknowledge','lab:view'],
    lab_tech: ['patient:view','lab:view','lab:result_enter'],
    viewer: ['patient:view','vitals:view','diagnosis:view'],
    admin:  ['ALL PERMISSIONS'],
  };
  return perms[role] || [];
}

// ── User Management Table ─────────────────────────────────
function UserManagement() {
  const [users, setUsers]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [roleFilter, setRoleFilter] = useState('');
  const [editRole, setEditRole] = useState({});  // userId → new role
  const [saving, setSaving]     = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await adminAPI.listUsers(roleFilter || undefined);
      setUsers(r.data.users || []);
    } catch { toast.error('Failed to load users'); }
    finally { setLoading(false); }
  }, [roleFilter]);

  useEffect(() => { load(); }, [load]);

  const saveRole = async (user) => {
    const newRole = editRole[user.id];
    if (!newRole || newRole === user.role) return;
    setSaving(user.id);
    try {
      await adminAPI.updateRole(user.id, newRole);
      toast.success(`${user.full_name} → ${newRole}`);
      setEditRole(e => { const n={...e}; delete n[user.id]; return n; });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Update failed'); }
    finally { setSaving(null); }
  };

  const toggleActive = async (user) => {
    try {
      await adminAPI.toggleActive(user.id);
      toast.success(`${user.full_name} ${user.is_active ? 'deactivated' : 'activated'}`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Toggle failed'); }
  };

  const s = {
    th: { padding:'11px 14px', color:'#334155', fontSize:10, fontWeight:700,
          letterSpacing:'0.6px', textAlign:'left', borderBottom:'1px solid #0EA5E920' },
    td: { padding:'12px 14px', borderBottom:'1px solid #ffffff05' },
    select: { padding:'5px 8px', borderRadius:7, background:'#060E1A',
      border:'1px solid #0EA5E925', color:'#F1F5F9', fontSize:11, outline:'none' },
  };

  return (
    <div>
      {/* Filters */}
      <div style={{ padding:'16px 20px', borderBottom:'1px solid #0EA5E920',
        display:'flex', gap:10, alignItems:'center' }}>
        <span style={{ color:'#64748B', fontSize:11 }}>FILTER BY ROLE:</span>
        {['', ...ROLES].map(r => (
          <button key={r} onClick={() => setRoleFilter(r)}
            style={{ padding:'4px 12px', borderRadius:20, cursor:'pointer', fontSize:11,
              border:`1px solid ${roleFilter === r ? '#0EA5E9' : '#0EA5E920'}`,
              background: roleFilter === r ? '#0EA5E920' : 'transparent',
              color: roleFilter === r ? '#38BDF8' : '#64748B', fontFamily:'inherit' }}>
            {r || 'ALL'}
          </button>
        ))}
        <span style={{ marginLeft:'auto', color:'#475569', fontSize:12 }}>{users.length} users</span>
      </div>

      {loading ? (
        <div style={{ padding:40, textAlign:'center', color:'#475569' }}>Loading...</div>
      ) : (
        <table style={{ width:'100%', borderCollapse:'collapse' }}>
          <thead>
            <tr>{['User','Email','Current Role','Department','Status','Approved','Actions'].map(h => (
              <th key={h} style={s.th}>{h.toUpperCase()}</th>
            ))}</tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}
                onMouseEnter={e => e.currentTarget.style.background='#0EA5E908'}
                onMouseLeave={e => e.currentTarget.style.background='none'}>
                <td style={s.td}>
                  <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <div style={{ width:30, height:30, borderRadius:8,
                      background: ROLE_BG[u.role]||'#64748B18',
                      display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}>
                      {u.role==='admin'?'👑':u.role==='doctor'?'👨‍⚕️':u.role==='nurse'?'👩‍⚕️':u.role==='lab_tech'?'🔬':'👁️'}
                    </div>
                    <div style={{ color:'#CBD5E1', fontWeight:600, fontSize:13 }}>{u.full_name}</div>
                  </div>
                </td>
                <td style={{ ...s.td, color:'#64748B', fontSize:11 }}>{u.email}</td>
                <td style={s.td}>
                  <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <select value={editRole[u.id] ?? u.role}
                      onChange={e => setEditRole(m => ({ ...m, [u.id]: e.target.value }))}
                      style={{ ...s.select, borderColor: editRole[u.id] && editRole[u.id]!==u.role ? '#EAB308' : '#0EA5E925' }}>
                      {ROLES.map(r => <option key={r} value={r}>{r.replace('_',' ').toUpperCase()}</option>)}
                    </select>
                    {editRole[u.id] && editRole[u.id] !== u.role && (
                      <button onClick={() => saveRole(u)} disabled={saving===u.id}
                        style={{ padding:'4px 10px', borderRadius:7, background:'#EAB30820',
                          color:'#FDE047', border:'1px solid #EAB30840', cursor:'pointer', fontSize:11 }}>
                        {saving===u.id ? '...' : 'Save'}
                      </button>
                    )}
                  </div>
                </td>
                <td style={{ ...s.td, color:'#64748B', fontSize:12 }}>{u.department || '—'}</td>
                <td style={s.td}>
                  <span style={{ padding:'3px 9px', borderRadius:20, fontSize:10, fontWeight:700,
                    background: u.is_active ? '#22C55E18':'#DC262618',
                    color: u.is_active ? '#4ADE80':'#F87171' }}>
                    {u.is_active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                </td>
                <td style={s.td}>
                  <Badge
                    label={u.approval_status || 'approved'}
                    color={{approved:'#22C55E',pending:'#EAB308',rejected:'#DC2626'}[u.approval_status]||'#64748B'}
                  />
                </td>
                <td style={s.td}>
                  {u.role !== 'admin' && (
                    <button onClick={() => toggleActive(u)}
                      style={{ padding:'5px 12px', borderRadius:7, cursor:'pointer', fontSize:11,
                        background: u.is_active ? '#DC262615':'#22C55E15',
                        color: u.is_active ? '#F87171':'#4ADE80',
                        border: `1px solid ${u.is_active?'#DC262630':'#22C55E30'}` }}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Permissions Matrix ────────────────────────────────────
function PermissionsMatrix() {
  const [matrix, setMatrix] = useState(null);
  const ROLE_LIST = ['admin','doctor','nurse','lab_tech','viewer'];

  useEffect(() => {
    adminAPI.permissions().then(r => setMatrix(r.data)).catch(() => {});
  }, []);

  if (!matrix) return <div style={{ padding:40, textAlign:'center', color:'#475569' }}>Loading...</div>;

  // Get all unique permissions
  const allPerms = [...new Set(Object.values(matrix.permissions).flat())].sort();

  return (
    <div style={{ padding:20, overflowX:'auto' }}>
      <p style={{ color:'#475569', fontSize:13, marginBottom:16 }}>
        Full permission matrix — showing what each role can and cannot do.
      </p>
      <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
        <thead>
          <tr style={{ borderBottom:'1px solid #0EA5E920' }}>
            <th style={{ padding:'10px 14px', color:'#64748B', textAlign:'left', fontWeight:700,
              fontSize:10, letterSpacing:'0.5px', minWidth:180 }}>PERMISSION</th>
            {ROLE_LIST.map(role => (
              <th key={role} style={{ padding:'10px 14px', textAlign:'center',
                color: ROLE_COLORS[role]||'#64748B', fontWeight:700, fontSize:10, letterSpacing:'0.5px' }}>
                {role.replace('_',' ').toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allPerms.map((perm, i) => (
            <tr key={perm} style={{ background: i%2===0 ? '#0EA5E904':'transparent',
              borderBottom:'1px solid #ffffff04' }}>
              <td style={{ padding:'8px 14px', color:'#94A3B8', fontFamily:'monospace', fontSize:11 }}>
                {perm}
              </td>
              {ROLE_LIST.map(role => {
                const has = matrix.permissions[role]?.includes(perm) || role === 'admin';
                return (
                  <td key={role} style={{ padding:'8px 14px', textAlign:'center' }}>
                    {has
                      ? <span style={{ color:'#4ADE80', fontSize:14 }}>✓</span>
                      : <span style={{ color:'#334155', fontSize:12 }}>—</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Admin Page ───────────────────────────────────────
export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab]         = useState('approval');
  const [pending, setPending] = useState(0);
  const [stats, setStats]     = useState(null);

  const loadStats = useCallback(async () => {
    try {
      const r = await adminAPI.stats();
      setStats(r.data);
      setPending(r.data.pending_approvals || 0);
    } catch {}
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  if (user?.role !== 'admin') {
    return (
      <div style={{ padding:60, textAlign:'center' }}>
        <div style={{ fontSize:48, marginBottom:12 }}>🔒</div>
        <h2 style={{ color:'#F87171', fontSize:20, fontWeight:700, marginBottom:8 }}>Access Denied</h2>
        <p style={{ color:'#475569', fontSize:14 }}>Admin panel requires administrator privileges.</p>
        <p style={{ color:'#334155', fontSize:13, marginTop:4 }}>Your role: <strong style={{color:'#0EA5E9'}}>{user?.role}</strong></p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom:24 }}>
        <h1 style={{ color:'#F1F5F9', fontSize:26, fontWeight:700, margin:'0 0 4px' }}>
          👑 Admin Control Panel
        </h1>
        <p style={{ color:'#475569', fontSize:13, margin:0 }}>
          RBAC Management · User Approvals · Permission Control
        </p>
      </div>

      {/* Stats row */}
      {stats && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:12, marginBottom:22 }}>
          {[
            { label:'Total Users',   val: stats.total_users,       color:'#0EA5E9' },
            { label:'Active',        val: stats.active_users,      color:'#22C55E' },
            { label:'Pending',       val: stats.pending_approvals, color:'#EAB308' },
            { label:'Doctors',       val: stats.by_role?.doctor||0,   color:'#0EA5E9' },
            { label:'Nurses',        val: stats.by_role?.nurse||0,    color:'#22C55E' },
            { label:'Lab Techs',     val: stats.by_role?.lab_tech||0, color:'#F97316' },
          ].map(({ label, val, color }) => (
            <div key={label} style={{ background:'linear-gradient(135deg,#0B1E3D,#071428)',
              border:'1px solid #0EA5E920', borderRadius:12, padding:'12px 16px' }}>
              <div style={{ color:'#475569', fontSize:9, fontWeight:700,
                letterSpacing:'0.6px', marginBottom:4 }}>{label.toUpperCase()}</div>
              <div style={{ color, fontSize:24, fontWeight:700, fontFamily:'monospace' }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display:'flex', gap:3, background:'#0B1E3D', padding:5,
        borderRadius:12, width:'fit-content', marginBottom:18 }}>
        <TabBtn label="Approval Desk"    active={tab==='approval'}    onClick={()=>setTab('approval')}    badge={pending}/>
        <TabBtn label="User Management"  active={tab==='users'}       onClick={()=>setTab('users')}/>
        <TabBtn label="Permissions Matrix" active={tab==='perms'}     onClick={()=>setTab('perms')}/>
      </div>

      {/* Tab content */}
      <Card style={{ overflow:'hidden' }}>
        {tab==='approval' && (
          <>
            <div style={{ padding:'14px 20px', borderBottom:'1px solid #0EA5E920',
              display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <span style={{ color:'#64748B', fontSize:11, fontWeight:700, letterSpacing:'0.6px' }}>
                PENDING SIGNUP APPROVALS
              </span>
              <span style={{ color:'#475569', fontSize:11 }}>
                Review and approve new user registrations before granting access
              </span>
            </div>
            <ApprovalDesk onRefresh={loadStats}/>
          </>
        )}
        {tab==='users' && (
          <>
            <div style={{ padding:'14px 20px', borderBottom:'1px solid #0EA5E920' }}>
              <span style={{ color:'#64748B', fontSize:11, fontWeight:700, letterSpacing:'0.6px' }}>
                ALL SYSTEM USERS — ROLE & ACCESS MANAGEMENT
              </span>
            </div>
            <UserManagement/>
          </>
        )}
        {tab==='perms' && (
          <>
            <div style={{ padding:'14px 20px', borderBottom:'1px solid #0EA5E920' }}>
              <span style={{ color:'#64748B', fontSize:11, fontWeight:700, letterSpacing:'0.6px' }}>
                RBAC PERMISSIONS MATRIX
              </span>
            </div>
            <PermissionsMatrix/>
          </>
        )}
      </Card>
    </div>
  );
}
