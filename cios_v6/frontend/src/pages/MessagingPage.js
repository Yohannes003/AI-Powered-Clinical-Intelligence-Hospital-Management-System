import React, { useState, useEffect, useRef, useCallback } from 'react';
import { messagingAPI } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

const ROLE_ICON  = { admin:'👑', doctor:'👨‍⚕️', nurse:'👩‍⚕️', lab_tech:'🔬', viewer:'👁️' };
const ROLE_COLOR = { admin:'#6366F1', doctor:'#0EA5E9', nurse:'#22C55E', lab_tech:'#F97316', viewer:'#64748B' };

/* ─── sub-components ──────────────────────────────────── */
const Avatar = ({ name='?', role, size=32 }) => {
  const initials = name.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
  const color = ROLE_COLOR[role] || '#0EA5E9';
  return (
    <div style={{ width:size, height:size, borderRadius:size*0.28, flexShrink:0,
      background:`${color}22`, border:`1px solid ${color}40`,
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize:size*0.38, fontWeight:700, color, userSelect:'none' }}>
      {initials}
    </div>
  );
};

const TimeAgo = ({ iso }) => {
  if (!iso) return null;
  const diff = (Date.now() - new Date(iso)) / 1000;
  const str  = diff < 60 ? 'just now'
    : diff < 3600    ? `${Math.floor(diff/60)}m ago`
    : diff < 86400   ? `${Math.floor(diff/3600)}h ago`
    : new Date(iso).toLocaleDateString();
  return <span style={{ color:'#334155', fontSize:10 }}>{str}</span>;
};

/* ─── Compose Modal ───────────────────────────────────── */
function ComposeModal({ users, onClose, onCreated }) {
  const [subject, setSubject]   = useState('');
  const [selected, setSelected] = useState([]);
  const [opening, setOpening]   = useState('');
  const [patientId, setPatient] = useState('');
  const [urgent, setUrgent]     = useState(false);
  const [search, setSearch]     = useState('');
  const [sending, setSending]   = useState(false);

  const filtered = users.filter(u =>
    !search || u.name.toLowerCase().includes(search.toLowerCase()) ||
    (u.department||'').toLowerCase().includes(search.toLowerCase()) ||
    u.role.toLowerCase().includes(search.toLowerCase())
  );

  const toggle = (u) =>
    setSelected(s => s.find(x=>x.id===u.id) ? s.filter(x=>x.id!==u.id) : [...s, u]);

  const send = async () => {
    if (!subject.trim())   return toast.error('Subject is required');
    if (!selected.length)  return toast.error('Select at least one recipient');
    setSending(true);
    try {
      const res = await messagingAPI.createConversation({
        subject, participant_ids: selected.map(u=>u.id),
        patient_id: patientId ? parseInt(patientId) : null,
        is_urgent: urgent, opening_message: opening || null,
      });
      toast.success('Conversation started');
      onCreated(res.data.conversation_id);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create conversation'); }
    finally { setSending(false); }
  };

  const s = {
    overlay: { position:'fixed', inset:0, background:'#000000B0', zIndex:200,
      display:'flex', alignItems:'center', justifyContent:'center' },
    box: { width:560, maxHeight:'85vh', overflow:'auto', background:'linear-gradient(135deg,#0B1E3D,#071428)',
      border:'1px solid #0EA5E930', borderRadius:18, padding:28 },
    inp: { width:'100%', padding:'9px 12px', borderRadius:9, background:'#060E1A',
      border:'1px solid #0EA5E920', color:'#F1F5F9', fontSize:13, outline:'none',
      boxSizing:'border-box', fontFamily:'inherit' },
    lbl: { color:'#64748B', fontSize:10, fontWeight:700, letterSpacing:'0.5px',
      display:'block', marginBottom:5 },
  };

  return (
    <div style={s.overlay} onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={s.box}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:20 }}>
          <h3 style={{ color:'#F1F5F9', fontSize:17, fontWeight:700, margin:0 }}>✉️ New Conversation</h3>
          <button onClick={onClose} style={{ background:'none', border:'none',
            color:'#64748B', fontSize:20, cursor:'pointer', lineHeight:1 }}>×</button>
        </div>

        {/* Subject */}
        <div style={{ marginBottom:14 }}>
          <label style={s.lbl}>SUBJECT *</label>
          <input value={subject} onChange={e=>setSubject(e.target.value)}
            placeholder="Re: Patient consultation, Urgent lab results..." style={s.inp}/>
        </div>

        {/* Recipients */}
        <div style={{ marginBottom:14 }}>
          <label style={s.lbl}>RECIPIENTS * ({selected.length} selected)</label>
          <input value={search} onChange={e=>setSearch(e.target.value)}
            placeholder="Search staff by name, role, department..."
            style={{ ...s.inp, marginBottom:8 }}/>
          <div style={{ maxHeight:160, overflow:'auto', border:'1px solid #0EA5E920',
            borderRadius:9, background:'#060E1A' }}>
            {filtered.map(u => {
              const sel = selected.find(x=>x.id===u.id);
              return (
                <div key={u.id} onClick={()=>toggle(u)}
                  style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 12px',
                    cursor:'pointer', borderBottom:'1px solid #0EA5E90a',
                    background: sel ? '#0EA5E912' : 'transparent',
                    transition:'background .1s' }}>
                  <Avatar name={u.name} role={u.role} size={28}/>
                  <div style={{ flex:1 }}>
                    <div style={{ color: sel ? '#38BDF8':'#CBD5E1', fontSize:12, fontWeight: sel?700:400 }}>
                      {u.name}
                    </div>
                    <div style={{ color:'#334155', fontSize:10 }}>
                      {ROLE_ICON[u.role]} {u.role.replace('_',' ')} {u.department ? `· ${u.department}`:''}
                    </div>
                  </div>
                  {sel && <span style={{ color:'#22C55E', fontSize:14 }}>✓</span>}
                </div>
              );
            })}
          </div>
          {selected.length > 0 && (
            <div style={{ display:'flex', flexWrap:'wrap', gap:5, marginTop:6 }}>
              {selected.map(u => (
                <span key={u.id} style={{ padding:'2px 8px', borderRadius:20, fontSize:11,
                  background:'#0EA5E918', color:'#38BDF8', border:'1px solid #0EA5E930',
                  display:'flex', alignItems:'center', gap:5 }}>
                  {u.name}
                  <span onClick={()=>toggle(u)} style={{ cursor:'pointer', color:'#64748B' }}>×</span>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Opening message */}
        <div style={{ marginBottom:14 }}>
          <label style={s.lbl}>OPENING MESSAGE</label>
          <textarea value={opening} onChange={e=>setOpening(e.target.value)} rows={3}
            placeholder="Type your message..."
            style={{ ...s.inp, resize:'vertical' }}/>
        </div>

        {/* Extras */}
        <div style={{ display:'flex', gap:16, marginBottom:20, alignItems:'center' }}>
          <div style={{ flex:1 }}>
            <label style={s.lbl}>PATIENT MRN (optional)</label>
            <input value={patientId} onChange={e=>setPatient(e.target.value)}
              placeholder="Patient ID..." style={s.inp}/>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:8, paddingTop:16 }}>
            <input type="checkbox" id="urgent-chk" checked={urgent}
              onChange={e=>setUrgent(e.target.checked)}
              style={{ width:15, height:15, cursor:'pointer' }}/>
            <label htmlFor="urgent-chk" style={{ color:'#F87171', fontSize:12,
              cursor:'pointer', fontWeight:600 }}>🚨 Urgent</label>
          </div>
        </div>

        <div style={{ display:'flex', gap:10 }}>
          <button onClick={onClose}
            style={{ flex:1, padding:11, borderRadius:10, background:'#1E3A5F',
              color:'#94A3B8', border:'none', cursor:'pointer', fontSize:13 }}>Cancel</button>
          <button onClick={send} disabled={sending}
            style={{ flex:2, padding:11, borderRadius:10, fontWeight:700, fontSize:13,
              border:'none', cursor: sending ? 'not-allowed':'pointer',
              background: sending ? '#1E3A5F' : 'linear-gradient(135deg,#0EA5E9,#6366F1)',
              color:'#fff' }}>
            {sending ? 'Sending...' : '✉️ Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Thread View ─────────────────────────────────────── */
function ThreadView({ conv, currentUser, onBack }) {
  const [messages, setMessages]   = useState([]);
  const [newMsg, setNewMsg]       = useState('');
  const [sending, setSending]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const bottomRef                 = useRef(null);

  const load = useCallback(async () => {
    try {
      const r = await messagingAPI.getMessages(conv.id);
      setMessages(r.data.messages || []);
    } catch {}
    finally { setLoading(false); }
  }, [conv.id]);

  useEffect(() => { load(); const t = setInterval(load, 8000); return ()=>clearInterval(t); }, [load]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    if (!newMsg.trim()) return;
    setSending(true);
    const optimistic = {
      id: Date.now(), body: newMsg.trim(), message_type:'text',
      sender: { id: currentUser.id, name: currentUser.full_name, role: currentUser.role },
      created_at: new Date().toISOString(),
    };
    setMessages(m => [...m, optimistic]);
    setNewMsg('');
    try {
      await messagingAPI.sendMessage(conv.id, newMsg.trim());
    } catch (e) {
      toast.error('Failed to send message');
      setMessages(m => m.filter(x => x.id !== optimistic.id));
    } finally { setSending(false); }
  };

  const otherParticipants = conv.participants?.filter(p => p.id !== currentUser.id) || [];

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%' }}>
      {/* Thread header */}
      <div style={{ padding:'14px 18px', borderBottom:'1px solid #0EA5E915',
        display:'flex', alignItems:'center', gap:12 }}>
        <button onClick={onBack} style={{ background:'none', border:'none',
          color:'#0EA5E9', cursor:'pointer', fontSize:18, lineHeight:1, padding:0 }}>←</button>
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            {conv.is_urgent && <span style={{ color:'#F87171', fontSize:11, fontWeight:700 }}>🚨 URGENT</span>}
            <span style={{ color:'#CBD5E1', fontWeight:700, fontSize:14 }}>{conv.subject}</span>
          </div>
          <div style={{ color:'#334155', fontSize:11, marginTop:2 }}>
            {otherParticipants.slice(0,3).map(p=>p.name).join(', ')}
            {otherParticipants.length > 3 && ` +${otherParticipants.length-3} more`}
            {conv.patient_id && <span style={{ color:'#0EA5E9', marginLeft:8 }}>· Patient #{conv.patient_id}</span>}
          </div>
        </div>
        <div style={{ fontSize:11, color:'#334155' }}>{messages.length} messages</div>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflow:'auto', padding:'16px 18px' }}>
        {loading ? (
          <div style={{ textAlign:'center', color:'#475569', padding:40 }}>Loading...</div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign:'center', color:'#475569', padding:40 }}>
            No messages yet. Start the conversation below.
          </div>
        ) : messages.map((m, i) => {
          const isMe = m.sender?.id === currentUser.id;
          const showAvatar = !isMe && (i === 0 || messages[i-1]?.sender?.id !== m.sender?.id);
          return (
            <div key={m.id} style={{ marginBottom:10, display:'flex',
              justifyContent: isMe ? 'flex-end' : 'flex-start',
              alignItems:'flex-end', gap:8 }}>
              {!isMe && <div style={{ width:28, flexShrink:0 }}>
                {showAvatar && <Avatar name={m.sender?.name||'?'} role={m.sender?.role} size={28}/>}
              </div>}
              <div style={{ maxWidth:'68%' }}>
                {showAvatar && !isMe && (
                  <div style={{ color:'#64748B', fontSize:10, marginBottom:3, marginLeft:2 }}>
                    {ROLE_ICON[m.sender?.role]} {m.sender?.name}
                  </div>
                )}
                <div style={{ padding:'9px 13px', borderRadius:12,
                  borderBottomRightRadius: isMe ? 3 : 12,
                  borderBottomLeftRadius:  isMe ? 12 : 3,
                  background: isMe
                    ? 'linear-gradient(135deg,#0EA5E9,#6366F1)'
                    : '#1E3A5F',
                  color: '#F1F5F9', fontSize:13, lineHeight:1.6,
                  wordBreak:'break-word' }}>
                  {m.body}
                </div>
                <div style={{ textAlign: isMe ? 'right':'left', marginTop:3 }}>
                  <TimeAgo iso={m.created_at}/>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef}/>
      </div>

      {/* Compose */}
      <form onSubmit={send}
        style={{ padding:'12px 16px', borderTop:'1px solid #0EA5E915',
          display:'flex', gap:10, alignItems:'flex-end' }}>
        <textarea
          value={newMsg}
          onChange={e=>setNewMsg(e.target.value)}
          onKeyDown={e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); send(e); }}}
          placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
          rows={2}
          style={{ flex:1, padding:'10px 12px', borderRadius:10, background:'#060E1A',
            border:'1px solid #0EA5E920', color:'#F1F5F9', fontSize:13, outline:'none',
            resize:'none', fontFamily:'inherit', lineHeight:1.5 }}
        />
        <button type="submit" disabled={sending || !newMsg.trim()}
          style={{ padding:'10px 18px', borderRadius:10, fontWeight:700, fontSize:13,
            border:'none', cursor: (!newMsg.trim()||sending) ? 'not-allowed':'pointer',
            background: (!newMsg.trim()||sending) ? '#1E3A5F' : 'linear-gradient(135deg,#0EA5E9,#6366F1)',
            color:'#fff', flexShrink:0, height:42 }}>
          ➤
        </button>
      </form>
    </div>
  );
}

/* ─── Main MessagingPage ──────────────────────────────── */
export default function MessagingPage() {
  const { user }                    = useAuth();
  const [conversations, setConvs]   = useState([]);
  const [selected, setSelected]     = useState(null);
  const [users, setUsers]           = useState([]);
  const [composing, setComposing]   = useState(false);
  const [loading, setLoading]       = useState(true);
  const [totalUnread, setUnread]    = useState(0);
  const [filterUnread, setFilter]   = useState(false);

  const loadConvs = useCallback(async () => {
    try {
      const r = await messagingAPI.listConversations({ unread_only: filterUnread });
      setConvs(r.data.conversations || []);
    } catch {}
    finally { setLoading(false); }
  }, [filterUnread]);

  useEffect(() => {
    loadConvs();
    messagingAPI.unreadCount().then(r => setUnread(r.data.unread_count || 0)).catch(()=>{});
    messagingAPI.getUsers().then(r => setUsers(r.data.users || [])).catch(()=>{});
    const t = setInterval(() => {
      loadConvs();
      messagingAPI.unreadCount().then(r => setUnread(r.data.unread_count || 0)).catch(()=>{});
    }, 15000);
    return () => clearInterval(t);
  }, [loadConvs]);

  const openConv = (conv) => {
    setSelected(conv);
    // Optimistically clear unread
    setConvs(cs => cs.map(c => c.id === conv.id ? { ...c, unread_count: 0 } : c));
  };

  const selectedConv = conversations.find(c => c.id === selected?.id) || selected;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 100px)' }}>
      {/* Page header */}
      {!selectedConv && (
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:18 }}>
          <div>
            <h1 style={{ color:'#F1F5F9', fontSize:24, fontWeight:700, margin:0 }}>
              💬 Clinical Messaging
            </h1>
            <p style={{ color:'#475569', fontSize:13, margin:'3px 0 0' }}>
              Secure staff communication · {totalUnread > 0 ? `${totalUnread} unread` : 'All read'}
            </p>
          </div>
          <div style={{ display:'flex', gap:10 }}>
            <button onClick={() => setFilter(f=>!f)}
              style={{ padding:'8px 16px', borderRadius:10, fontSize:12, cursor:'pointer', fontFamily:'inherit',
                border:`1px solid ${filterUnread ? '#0EA5E9':'#0EA5E920'}`,
                background: filterUnread ? '#0EA5E918':'transparent',
                color: filterUnread ? '#38BDF8':'#64748B', fontWeight: filterUnread?700:400 }}>
              Unread only {totalUnread > 0 && `(${totalUnread})`}
            </button>
            <button onClick={() => setComposing(true)}
              style={{ padding:'9px 20px', borderRadius:10, fontWeight:700, fontSize:13,
                background:'linear-gradient(135deg,#0EA5E9,#6366F1)',
                color:'#fff', border:'none', cursor:'pointer' }}>
              ✉️ New Message
            </button>
          </div>
        </div>
      )}

      {/* Main panel */}
      <div style={{ flex:1, display:'flex', background:'linear-gradient(135deg,#0B1E3D,#071428)',
        border:'1px solid #0EA5E920', borderRadius:16, overflow:'hidden', minHeight:0 }}>

        {/* Conversation list */}
        {!selectedConv && (
          <div style={{ width:'100%', overflow:'auto' }}>
            {loading ? (
              <div style={{ padding:40, textAlign:'center', color:'#475569' }}>Loading...</div>
            ) : conversations.length === 0 ? (
              <div style={{ padding:60, textAlign:'center' }}>
                <div style={{ fontSize:48, marginBottom:12 }}>💬</div>
                <p style={{ color:'#475569', fontSize:14 }}>
                  {filterUnread ? 'No unread messages' : 'No conversations yet'}
                </p>
                <button onClick={() => setComposing(true)}
                  style={{ marginTop:12, padding:'9px 20px', borderRadius:10, fontWeight:700,
                    background:'linear-gradient(135deg,#0EA5E9,#6366F1)', color:'#fff',
                    border:'none', cursor:'pointer', fontSize:13 }}>
                  Start a conversation
                </button>
              </div>
            ) : conversations.map(conv => {
              const others = conv.participants?.filter(p=>p.id!==user?.id) || [];
              return (
                <div key={conv.id} onClick={() => openConv(conv)}
                  style={{ display:'flex', gap:12, alignItems:'flex-start',
                    padding:'14px 18px', cursor:'pointer', transition:'background .15s',
                    borderBottom:'1px solid #0EA5E90a',
                    background: conv.unread_count > 0 ? '#0EA5E905' : 'transparent' }}
                  onMouseEnter={e=>e.currentTarget.style.background='#0EA5E90a'}
                  onMouseLeave={e=>e.currentTarget.style.background= conv.unread_count>0 ? '#0EA5E905':'transparent'}>

                  {/* Avatar group */}
                  <div style={{ position:'relative', width:40, height:40, flexShrink:0 }}>
                    <Avatar name={others[0]?.name||'?'} role={others[0]?.role} size={36}/>
                    {others.length > 1 && (
                      <div style={{ position:'absolute', bottom:-2, right:-2, width:18, height:18,
                        borderRadius:9, background:'#1E3A5F', border:'2px solid #0B1E3D',
                        display:'flex', alignItems:'center', justifyContent:'center',
                        color:'#94A3B8', fontSize:9, fontWeight:700 }}>
                        +{others.length-1}
                      </div>
                    )}
                  </div>

                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                        {conv.is_urgent && <span style={{ fontSize:11 }}>🚨</span>}
                        <span style={{ color: conv.unread_count>0 ? '#F1F5F9':'#94A3B8',
                          fontWeight: conv.unread_count>0 ? 700:500, fontSize:13,
                          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
                          maxWidth:320 }}>
                          {conv.subject}
                        </span>
                      </div>
                      <div style={{ display:'flex', gap:8, alignItems:'center', flexShrink:0 }}>
                        {conv.unread_count > 0 && (
                          <span style={{ background:'#0EA5E9', color:'#fff', borderRadius:20,
                            padding:'1px 7px', fontSize:10, fontWeight:700 }}>
                            {conv.unread_count}
                          </span>
                        )}
                        <TimeAgo iso={conv.last_message?.created_at || conv.created_at}/>
                      </div>
                    </div>
                    <div style={{ color:'#334155', fontSize:11, marginTop:2 }}>
                      {others.map(p=>p.name).slice(0,2).join(', ')}
                      {conv.patient_id && <span style={{ color:'#0EA5E9', marginLeft:6 }}>· Patient #{conv.patient_id}</span>}
                    </div>
                    {conv.last_message && (
                      <div style={{ color:'#475569', fontSize:12, marginTop:3,
                        overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                        {conv.last_message.sender_id === user?.id ? 'You: ' : ''}
                        {conv.last_message.body}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Thread view */}
        {selectedConv && (
          <div style={{ width:'100%', display:'flex', flexDirection:'column', minHeight:0 }}>
            <ThreadView
              conv={selectedConv}
              currentUser={user}
              onBack={() => { setSelected(null); loadConvs(); }}
            />
          </div>
        )}
      </div>

      {/* Compose modal */}
      {composing && (
        <ComposeModal
          users={users}
          onClose={() => setComposing(false)}
          onCreated={(id) => {
            setComposing(false);
            loadConvs();
            // Auto-open new conversation
            setTimeout(() => {
              messagingAPI.listConversations()
                .then(r => {
                  const convs = r.data.conversations || [];
                  const newConv = convs.find(c => c.id === id);
                  if (newConv) setSelected(newConv);
                  setConvs(convs);
                });
            }, 500);
          }}
        />
      )}
    </div>
  );
}
