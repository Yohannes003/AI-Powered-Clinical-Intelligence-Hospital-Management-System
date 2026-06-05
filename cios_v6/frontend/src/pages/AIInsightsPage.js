import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiAPI } from '../api/client';
import toast from 'react-hot-toast';

const RISK_COLORS = { stable: '#22C55E', moderate: '#F97316', critical: '#DC2626', low: '#22C55E', medium: '#EAB308', high: '#F97316' };

export default function AIInsightsPage() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(null);
  const [reviewNote, setReviewNote] = useState('');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const res = await aiAPI.getPendingReviews();
      setReviews(res.data.pending || []);
    } catch (e) { toast.error('Failed to load pending reviews'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const submitReview = async (predId) => {
    if (!reviewNote.trim()) return toast.error('Please add review notes');
    try {
      await aiAPI.submitReview(predId, reviewNote);
      toast.success('Review submitted');
      setReviewing(null);
      setReviewNote('');
      load();
    } catch (e) { toast.error('Review failed'); }
  };

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ color: '#F1F5F9', fontSize: 26, fontWeight: 700, margin: 0 }}>🧠 AI Clinical Intelligence</h1>
        <p style={{ color: '#475569', fontSize: 13, margin: '4px 0 0' }}>
          Pending physician reviews · Human-in-the-loop validation · {reviews.length} awaiting review
        </p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Pending Reviews', value: reviews.length, color: '#EAB308', icon: '⏳' },
          { label: 'Moderate Risk', value: reviews.filter(r => r.risk_level === 'moderate' || r.risk_level === 'medium' || r.risk_level === 'high').length, color: '#F97316', icon: '🟡' },
          { label: 'Critical', value: reviews.filter(r => r.risk_level === 'critical').length, color: '#DC2626', icon: '🚨' },
          { label: 'Avg Confidence', value: reviews.length ? `${(reviews.reduce((a, r) => a + r.confidence_score, 0) / reviews.length * 100).toFixed(0)}%` : '—', color: '#0EA5E9', icon: '📊' },
        ].map(({ label, value, color, icon }) => (
          <div key={label} style={{ background: 'linear-gradient(135deg, #0B1E3D, #071428)', border: '1px solid #0EA5E920', borderRadius: 14, padding: '16px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ color: '#64748B', fontSize: 11, fontWeight: 700, letterSpacing: '0.5px' }}>{label.toUpperCase()}</div>
                <div style={{ color: color, fontSize: 28, fontWeight: 800, lineHeight: 1.2 }}>{value}</div>
              </div>
              <div style={{ fontSize: 28 }}>{icon}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Review queue */}
      <div style={{ background: 'linear-gradient(135deg, #0B1E3D, #071428)', border: '1px solid #0EA5E920', borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #0EA5E920', display: 'flex', justifyContent: 'space-between' }}>
          <h3 style={{ color: '#94A3B8', fontSize: 13, fontWeight: 700, letterSpacing: '0.5px', margin: 0 }}>HUMAN REVIEW QUEUE</h3>
          <span style={{ color: '#64748B', fontSize: 12 }}>AI confidence &lt; 75% threshold requires physician validation</span>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#475569' }}>Loading...</div>
        ) : reviews.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <p style={{ color: '#4ADE80', fontSize: 16, fontWeight: 600 }}>All AI predictions reviewed!</p>
            <p style={{ color: '#475569', fontSize: 13 }}>No pending cases in the review queue.</p>
          </div>
        ) : (
          reviews.map(r => {
            const rColor = RISK_COLORS[r.risk_level] || '#0EA5E9';
            const isExpanded = reviewing === r.id;

            return (
              <div key={r.id} style={{ padding: '18px 20px', borderBottom: '1px solid #0EA5E910' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                      <button onClick={() => navigate(`/patients/${r.patient_id}`)}
                        style={{ background: 'none', border: 'none', color: '#38BDF8', cursor: 'pointer', fontSize: 15, fontWeight: 700, padding: 0 }}>
                        Patient #{r.patient_id}
                      </button>
                      <span style={{ padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 800, background: rColor + '25', color: rColor, border: `1px solid ${rColor}40` }}>
                        {r.risk_level?.toUpperCase()}
                      </span>
                      <span style={{ color: '#475569', fontSize: 12 }}>Score: {(r.risk_score * 100).toFixed(0)}%</span>
                      <span style={{ color: '#EAB308', fontSize: 12 }}>Confidence: {(r.confidence_score * 100).toFixed(0)}%</span>
                      <span style={{ color: '#475569', fontSize: 11 }}>{new Date(r.created_at).toLocaleString()}</span>
                    </div>

                    {/* Explanation */}
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                      {(r.explanation || []).slice(0, 3).map((e, i) => (
                        <span key={i} style={{ padding: '2px 8px', background: '#F9731610', border: '1px solid #F9731630', borderRadius: 20, color: '#94A3B8', fontSize: 11 }}>
                          {e}
                        </span>
                      ))}
                    </div>

                    {/* Recommendations */}
                    {(r.recommendations || []).slice(0, 2).map((rec, i) => (
                      <div key={i} style={{ color: '#64748B', fontSize: 12 }}>→ {rec}</div>
                    ))}
                  </div>

                  <button onClick={() => { setReviewing(isExpanded ? null : r.id); setReviewNote(''); }}
                    style={{ padding: '8px 16px', borderRadius: 10, background: isExpanded ? '#1E3A5F' : 'linear-gradient(135deg, #0EA5E9, #6366F1)', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer', fontSize: 13, flexShrink: 0, marginLeft: 12 }}>
                    {isExpanded ? 'Cancel' : 'Review'}
                  </button>
                </div>

                {isExpanded && (
                  <div style={{ marginTop: 16, padding: 16, background: '#060E1A', borderRadius: 10, border: '1px solid #0EA5E920' }}>
                    <label style={{ color: '#64748B', fontSize: 11, fontWeight: 700, display: 'block', marginBottom: 8, letterSpacing: '0.5px' }}>
                      PHYSICIAN REVIEW NOTES *
                    </label>
                    <textarea value={reviewNote} onChange={e => setReviewNote(e.target.value)}
                      placeholder="Enter your clinical assessment and whether you agree with the AI risk assessment..."
                      rows={3}
                      style={{ width: '100%', padding: '10px 12px', borderRadius: 8, background: '#0B1E3D', border: '1px solid #0EA5E925', color: '#F1F5F9', fontSize: 13, outline: 'none', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }}
                    />
                    <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                      <button onClick={() => submitReview(r.id)}
                        style={{ flex: 1, padding: '9px', borderRadius: 9, background: '#22C55E', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer', fontSize: 13 }}>
                        ✓ Approve & Submit Review
                      </button>
                      <button onClick={() => { setReviewing(null); setReviewNote(''); }}
                        style={{ padding: '9px 16px', borderRadius: 9, background: '#1E3A5F', color: '#94A3B8', border: 'none', cursor: 'pointer', fontSize: 13 }}>
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
