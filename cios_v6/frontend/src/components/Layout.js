import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { adminAPI, messagingAPI } from '../api/client';

export default function Layout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed]     = useState(false);
  const [pendingCount, setPending]    = useState(0);
  const [unreadCount, setUnread]      = useState(0);

  useEffect(() => {
    const fetchBadges = async () => {
      try {
        const msgRes = await messagingAPI.unreadCount();
        setUnread(msgRes.data.unread_count || 0);
      } catch {}
      if (user?.role === 'admin') {
        try {
          const admRes = await adminAPI.getPending();
          setPending(admRes.data.count || 0);
        } catch {}
      }
    };
    fetchBadges();
    const t = setInterval(fetchBadges, 20000);
    return () => clearInterval(t);
  }, [user]);

  const handleLogout = () => { logout(); navigate('/login'); };

  const ROLE_COLOR = { admin:'#6366F1', doctor:'#0EA5E9', nurse:'#22C55E', lab_tech:'#F97316', viewer:'#64748B' };
  const ROLE_ICON  = { admin:'👑', doctor:'👨‍⚕️', nurse:'👩‍⚕️', lab_tech:'🔬', viewer:'👁️' };
  const rc = ROLE_COLOR[user?.role] || '#0EA5E9';

  const navItems = [
    { to:'/',           label:'Dashboard',   icon:'⬡',  show: true },
    { to:'/patients',   label:'Patients',    icon:'👤',  show: can('patient:view') },
    { to:'/messaging',  label:'Messages',    icon:'💬',  show: true,  badge: unreadCount },
    { to:'/referrals',  label:'Referrals',   icon:'📋',  show: can('diagnosis:view') || can('diagnosis:add') },
    { to:'/ai-insights',label:'AI Insights', icon:'🧠',  show: can('ai:view') || can('ai:assess') },
    { to:'/reports',    label:'Reports',     icon:'📊',  show: can('report:view') || can('report:generate') },
    { to:'/admin',      label:'Admin Panel', icon:'👑',  show: user?.role === 'admin', badge: pendingCount },
  ].filter(n => n.show);

  const NavItem = ({ to, label, icon, badge }) => (
    <NavLink to={to} end={to === '/'}
      style={({ isActive }) => ({
        display:'flex', alignItems:'center', gap:10, padding:'9px 10px',
        borderRadius:9, marginBottom:2, textDecoration:'none', transition:'all 0.15s',
        background: isActive ? 'linear-gradient(90deg,#0EA5E918,#6366F110)' : 'transparent',
        color: isActive ? '#38BDF8' : '#475569',
        borderLeft: isActive ? '2px solid #0EA5E9' : '2px solid transparent',
        fontWeight: isActive ? 600 : 400, fontSize: 13, position:'relative',
      })}>
      <span style={{ fontSize:16, flexShrink:0, width:20, textAlign:'center' }}>{icon}</span>
      {!collapsed && <span style={{ flex:1 }}>{label}</span>}
      {!collapsed && badge > 0 && (
        <span style={{ background:'#DC2626', color:'#fff', borderRadius:20,
          padding:'1px 7px', fontSize:10, fontWeight:700, minWidth:20, textAlign:'center' }}>
          {badge > 99 ? '99+' : badge}
        </span>
      )}
      {collapsed && badge > 0 && (
        <span style={{ position:'absolute', top:4, right:4, background:'#DC2626',
          width:8, height:8, borderRadius:'50%' }}/>
      )}
    </NavLink>
  );

  return (
    <div style={{ display:'flex', height:'100vh', background:'#060E1A',
      fontFamily:"'Segoe UI',sans-serif", overflow:'hidden' }}>

      {/* ── Sidebar ─────────────────────────────────── */}
      <aside style={{ width: collapsed ? 60 : 222, flexShrink:0, transition:'width .2s ease',
        background:'linear-gradient(180deg,#0B1E3D,#071428)',
        borderRight:'1px solid #0EA5E912', display:'flex', flexDirection:'column' }}>

        {/* Logo */}
        <div style={{ padding:'15px 12px', borderBottom:'1px solid #0EA5E910',
          display:'flex', alignItems:'center', gap:10 }}>
          <div style={{ width:34, height:34, borderRadius:10, flexShrink:0,
            background:'linear-gradient(135deg,#0EA5E9,#6366F1)',
            display:'flex', alignItems:'center', justifyContent:'center', fontSize:17 }}>🏥</div>
          {!collapsed && (
            <div>
              <div style={{ color:'#F1F5F9', fontWeight:700, fontSize:14, lineHeight:1.2 }}>CIOS</div>
              <div style={{ color:'#334155', fontSize:9, letterSpacing:'1px' }}>CLINICAL OS</div>
            </div>
          )}
          <button onClick={() => setCollapsed(c => !c)}
            style={{ marginLeft:'auto', background:'none', border:'none',
              color:'#334155', cursor:'pointer', fontSize:16, padding:0, lineHeight:1 }}>
            {collapsed ? '→' : '←'}
          </button>
        </div>

        {/* Status + role */}
        {!collapsed && (
          <div style={{ margin:'8px 8px 4px' }}>
            <div style={{ padding:'4px 10px', borderRadius:8, background:'#22C55E08',
              border:'1px solid #22C55E20', display:'flex', alignItems:'center', gap:6 }}>
              <div style={{ width:5, height:5, borderRadius:'50%', background:'#22C55E',
                animation:'pulse 2s infinite' }}/>
              <span style={{ color:'#4ADE80', fontSize:9, fontWeight:600, letterSpacing:'.5px' }}>
                SYSTEMS LIVE
              </span>
            </div>
            <div style={{ marginTop:5, padding:'4px 10px', borderRadius:8,
              background:`${rc}10`, border:`1px solid ${rc}25`,
              display:'flex', alignItems:'center', gap:6 }}>
              <span style={{ fontSize:12 }}>{ROLE_ICON[user?.role]}</span>
              <span style={{ color:rc, fontSize:10, fontWeight:700 }}>
                {user?.role?.replace('_',' ').toUpperCase()}
              </span>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav style={{ flex:1, padding:'8px 6px', overflowY:'auto' }}>
          {navItems.map(item => <NavItem key={item.to} {...item}/>)}
        </nav>

        {/* User footer */}
        <div style={{ padding:'10px 6px', borderTop:'1px solid #0EA5E910' }}>
          {!collapsed && (
            <div style={{ display:'flex', alignItems:'center', gap:8,
              padding:'7px 10px', marginBottom:6 }}>
              <div style={{ width:28, height:28, borderRadius:8, flexShrink:0,
                background:`${rc}25`, border:`1px solid ${rc}35`,
                display:'flex', alignItems:'center', justifyContent:'center', fontSize:13 }}>
                {ROLE_ICON[user?.role]}
              </div>
              <div style={{ overflow:'hidden' }}>
                <div style={{ color:'#94A3B8', fontSize:12, fontWeight:600,
                  overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:130 }}>
                  {user?.full_name}
                </div>
                <div style={{ color:'#334155', fontSize:10 }}>
                  {user?.department || user?.role?.replace('_',' ')}
                </div>
              </div>
            </div>
          )}
          <button onClick={handleLogout}
            style={{ width:'100%', padding: collapsed ? '8px 0' : '7px 10px', borderRadius:8,
              border:'none', background:'#DC262610', color:'#F87171', cursor:'pointer',
              fontSize:12, display:'flex', alignItems:'center',
              justifyContent: collapsed ? 'center' : 'flex-start', gap:8, fontFamily:'inherit' }}>
            <span style={{ fontSize:14 }}>🚪</span>
            {!collapsed && 'Sign Out'}
          </button>
        </div>
      </aside>

      {/* ── Main content ──────────────────────────── */}
      <main style={{ flex:1, overflow:'auto', display:'flex', flexDirection:'column' }}>
        {/* Topbar */}
        <div style={{ height:52, flexShrink:0, background:'#0B1E3D80',
          backdropFilter:'blur(12px)', borderBottom:'1px solid #0EA5E910',
          display:'flex', alignItems:'center', padding:'0 22px', gap:12,
          position:'sticky', top:0, zIndex:10 }}>
          <span style={{ color:'#334155', fontSize:11 }}>
            {new Date().toLocaleDateString('en-US', {
              weekday:'long', year:'numeric', month:'long', day:'numeric'
            })}
          </span>
          <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center' }}>
            {unreadCount > 0 && (
              <div onClick={() => navigate('/messaging')}
                style={{ padding:'4px 12px', borderRadius:20, background:'#0EA5E915',
                  border:'1px solid #0EA5E930', color:'#38BDF8', fontSize:11,
                  fontWeight:600, cursor:'pointer', display:'flex', alignItems:'center', gap:5 }}>
                💬 {unreadCount} unread
              </div>
            )}
            {user?.role === 'admin' && pendingCount > 0 && (
              <div onClick={() => navigate('/admin')}
                style={{ padding:'4px 12px', borderRadius:20, background:'#EAB30815',
                  border:'1px solid #EAB30830', color:'#FDE047', fontSize:11,
                  fontWeight:600, cursor:'pointer' }}>
                ⏳ {pendingCount} pending
              </div>
            )}
            <div style={{ padding:'4px 12px', borderRadius:20, background:'#22C55E15',
              border:'1px solid #22C55E30', color:'#4ADE80', fontSize:11, fontWeight:600 }}>
              ● AI ACTIVE
            </div>
          </div>
        </div>

        {/* Page */}
        <div style={{ flex:1, padding:'22px', minHeight:0, overflowY:'auto' }}>
          <Outlet />
        </div>
      </main>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        nav::-webkit-scrollbar { width:3px }
        nav::-webkit-scrollbar-track { background:transparent }
        nav::-webkit-scrollbar-thumb { background:#1E3A5F; border-radius:3px }
      `}</style>
    </div>
  );
}
