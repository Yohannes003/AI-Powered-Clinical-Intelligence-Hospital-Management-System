import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

const ROLES = [
  { value:'doctor',   label:'Doctor',          icon:'👨‍⚕️' },
  { value:'nurse',    label:'Nurse',            icon:'👩‍⚕️' },
  { value:'lab_tech', label:'Lab Technician',   icon:'🔬' },
  { value:'viewer',   label:'Viewer / Staff',   icon:'👁️' },
];

export default function LoginPage() {
  const [mode, setMode]         = useState('login');   // login | register
  const [email, setEmail]       = useState('doctor@cios.hospital');
  const [password, setPassword] = useState('Doctor@123');
  const [fullName, setFullName] = useState('');
  const [role, setRole]         = useState('doctor');
  const [department, setDept]   = useState('');
  const [license, setLicense]   = useState('');
  const [loading, setLoading]   = useState(false);
  const { login }               = useAuth();
  const navigate                = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      toast.success(`Welcome back, ${result.user?.full_name?.split(' ')[0]}!`);
      navigate('/');
    } else {
      toast.error(result.error || 'Login failed');
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { authAPI } = await import('../api/client');
      const res = await authAPI.register({ email, full_name: fullName, password, role, department, license_number: license });
      toast.success('Registration submitted! Waiting for admin approval.', { duration: 6000 });
      setMode('pending');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const bg = { minHeight:'100vh', background:'radial-gradient(ellipse at 20% 50%,#0B1E3D 0%,#060E1A 60%,#030810 100%)', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:"'Segoe UI',sans-serif", position:'relative' };
  const grid = { position:'fixed', inset:0, opacity:0.04, backgroundImage:'linear-gradient(#0EA5E9 1px,transparent 1px),linear-gradient(90deg,#0EA5E9 1px,transparent 1px)', backgroundSize:'40px 40px', pointerEvents:'none' };
  const card = { width:420, padding:36, background:'linear-gradient(135deg,#0B1E3D,#071428)', border:'1px solid #0EA5E930', borderRadius:20, boxShadow:'0 25px 80px #000000A0,0 0 40px #0EA5E910', position:'relative', zIndex:1 };
  const inp = { width:'100%', padding:'11px 12px', borderRadius:10, background:'#060E1A', border:'1px solid #0EA5E925', color:'#F1F5F9', fontSize:13, outline:'none', boxSizing:'border-box', fontFamily:'inherit' };
  const lbl = { color:'#94A3B8', fontSize:11, fontWeight:600, display:'block', marginBottom:5, letterSpacing:'0.5px' };
  const btn = { width:'100%', padding:13, borderRadius:10, background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff', fontWeight:700, fontSize:14, border:'none', cursor:'pointer', marginTop:8 };

  // ── Pending approval screen ───────────────────────────
  if (mode === 'pending') return (
    <div style={bg}>
      <div style={grid}/>
      <div style={card}>
        <div style={{ textAlign:'center', padding:'20px 0' }}>
          <div style={{ fontSize:52, marginBottom:16 }}>⏳</div>
          <h2 style={{ color:'#F1F5F9', fontSize:22, fontWeight:700, margin:'0 0 10px' }}>Registration Submitted</h2>
          <p style={{ color:'#64748B', fontSize:14, lineHeight:1.7 }}>
            Your account is <strong style={{color:'#EAB308'}}>pending admin approval</strong>.<br/>
            You will be notified once an administrator reviews your request.
          </p>
          <div style={{ marginTop:20, padding:14, background:'#EAB30810', border:'1px solid #EAB30830', borderRadius:10 }}>
            <p style={{ color:'#FDE047', fontSize:12, margin:0, lineHeight:1.7 }}>
              📧 Submitted as: <strong>{email}</strong><br/>
              🏷️ Role requested: <strong>{role.replace('_',' ').toUpperCase()}</strong>
            </p>
          </div>
          <button onClick={() => setMode('login')} style={{ ...btn, marginTop:20, background:'linear-gradient(135deg,#1E3A5F,#0B1E3D)', border:'1px solid #0EA5E930' }}>
            ← Back to Login
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div style={bg}>
      <div style={grid}/>
      <div style={card}>
        {/* Logo */}
        <div style={{ textAlign:'center', marginBottom:28 }}>
          <div style={{ width:60, height:60, borderRadius:16, background:'linear-gradient(135deg,#0EA5E9,#6366F1)', display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:28, marginBottom:10, boxShadow:'0 8px 24px #0EA5E940' }}>🏥</div>
          <h1 style={{ color:'#F1F5F9', fontSize:22, fontWeight:700, margin:0 }}>CIOS</h1>
          <p style={{ color:'#475569', fontSize:11, margin:'3px 0 0', letterSpacing:'1.2px' }}>CLINICAL INTELLIGENCE OS</p>
        </div>

        {/* Mode toggle */}
        <div style={{ display:'flex', background:'#060E1A', borderRadius:10, padding:4, marginBottom:22 }}>
          {[['login','Sign In'],['register','Register']].map(([m, label]) => (
            <button key={m} onClick={() => setMode(m)} style={{
              flex:1, padding:'8px', borderRadius:8, border:'none', cursor:'pointer', fontSize:13, fontFamily:'inherit',
              background: mode===m ? 'linear-gradient(135deg,#0EA5E9,#6366F1)' : 'transparent',
              color: mode===m ? '#fff' : '#64748B', fontWeight: mode===m ? 700 : 400,
            }}>{label}</button>
          ))}
        </div>

        {/* LOGIN FORM */}
        {mode === 'login' && (
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom:14 }}>
              <label style={lbl}>EMAIL</label>
              <input type="email" value={email} required onChange={e=>setEmail(e.target.value)}
                style={inp} onFocus={e=>e.target.style.borderColor='#0EA5E9'} onBlur={e=>e.target.style.borderColor='#0EA5E925'}/>
            </div>
            <div style={{ marginBottom:16 }}>
              <label style={lbl}>PASSWORD</label>
              <input type="password" value={password} required onChange={e=>setPassword(e.target.value)}
                style={inp} onFocus={e=>e.target.style.borderColor='#0EA5E9'} onBlur={e=>e.target.style.borderColor='#0EA5E925'}/>
            </div>
            <button type="submit" disabled={loading} style={{ ...btn, opacity: loading ? 0.7 : 1, cursor: loading ? 'not-allowed':'pointer' }}>
              {loading ? 'Signing in...' : 'Sign In to CIOS'}
            </button>
            {/* Demo creds */}
            <div style={{ marginTop:18, padding:14, background:'#0EA5E908', border:'1px solid #0EA5E915', borderRadius:10 }}>
              <p style={{ color:'#475569', fontSize:10, margin:'0 0 6px', fontWeight:700, letterSpacing:'0.5px' }}>DEMO CREDENTIALS</p>
              {[['Admin','admin@cios.hospital','Admin@123','#6366F1'],['Doctor','doctor@cios.hospital','Doctor@123','#0EA5E9'],['Nurse','nurse@cios.hospital','Nurse@123','#22C55E']].map(([role,em,pw,c])=>(
                <div key={role} onClick={() => { setEmail(em); setPassword(pw); }}
                  style={{ display:'flex', justifyContent:'space-between', padding:'4px 0', cursor:'pointer', borderBottom:'1px solid #ffffff05' }}>
                  <span style={{ color:c, fontSize:11, fontWeight:600 }}>{role}</span>
                  <span style={{ color:'#334155', fontSize:10, fontFamily:'monospace' }}>{em}</span>
                </div>
              ))}
              <p style={{ color:'#334155', fontSize:9, margin:'5px 0 0' }}>Click a row to auto-fill</p>
            </div>
          </form>
        )}

        {/* REGISTER FORM */}
        {mode === 'register' && (
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>FULL NAME *</label>
              <input type="text" value={fullName} required onChange={e=>setFullName(e.target.value)}
                placeholder="Dr. John Smith" style={inp}/>
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>EMAIL ADDRESS *</label>
              <input type="email" value={email} required onChange={e=>setEmail(e.target.value)}
                placeholder="you@hospital.com" style={inp}/>
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>PASSWORD *</label>
              <input type="password" value={password} required onChange={e=>setPassword(e.target.value)}
                placeholder="Min 8 characters" style={inp}/>
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>ROLE *</label>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6 }}>
                {ROLES.map(r => (
                  <button key={r.value} type="button" onClick={() => setRole(r.value)}
                    style={{ padding:'8px 10px', borderRadius:9, cursor:'pointer', fontSize:12, fontFamily:'inherit', textAlign:'left',
                      border:`2px solid ${role===r.value ? '#0EA5E9' : '#0EA5E920'}`,
                      background: role===r.value ? '#0EA5E918' : 'transparent',
                      color: role===r.value ? '#38BDF8' : '#64748B', fontWeight: role===r.value ? 700:400 }}>
                    {r.icon} {r.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
              <div>
                <label style={lbl}>DEPARTMENT</label>
                <input type="text" value={department} onChange={e=>setDept(e.target.value)}
                  placeholder="Cardiology..." style={inp}/>
              </div>
              <div>
                <label style={lbl}>LICENSE NO.</label>
                <input type="text" value={license} onChange={e=>setLicense(e.target.value)}
                  placeholder="MD-2024-..." style={inp}/>
              </div>
            </div>
            <div style={{ padding:10, background:'#EAB30808', border:'1px solid #EAB30820', borderRadius:8, marginBottom:12 }}>
              <p style={{ color:'#FDE047', fontSize:11, margin:0, lineHeight:1.6 }}>
                ⚠️ Your account will be <strong>pending admin approval</strong> after registration. You cannot log in until an administrator approves your request.
              </p>
            </div>
            <button type="submit" disabled={loading} style={{ ...btn, opacity: loading ? 0.7:1, cursor: loading?'not-allowed':'pointer' }}>
              {loading ? 'Submitting...' : 'Submit Registration Request'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
