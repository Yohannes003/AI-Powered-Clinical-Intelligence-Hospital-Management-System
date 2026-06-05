import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('cios_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// Auto-logout on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cios_token');
      localStorage.removeItem('cios_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Auth ────────────────────────────────────────────────
export const authAPI = {
  login:    (email, password) => api.post('/auth/login', { email, password }),
  register: (data)            => api.post('/auth/register', data),
  me:       ()                => api.get('/auth/me'),
};

// ─── Patients ────────────────────────────────────────────
export const patientAPI = {
  list:         (params) => api.get('/patients/', { params }),
  get:          (id)     => api.get(`/patients/${id}`),
  create:       (data)   => api.post('/patients/', data),
  update:       (id, data) => api.put(`/patients/${id}`, data),
  stats:        ()       => api.get('/patients/dashboard/stats'),
  recordVitals: (id, data) => api.post(`/patients/${id}/vitals`, data),
  getVitals:    (id, limit = 20) => api.get(`/patients/${id}/vitals`, { params: { limit } }),
  getAuditTrail:(id) => api.get(`/patients/${id}/audit-trail`),
};

// ─── Clinical ────────────────────────────────────────────
export const clinicalAPI = {
  addDiagnosis:     (data)      => api.post('/clinical/diagnoses', data),
  getDiagnoses:     (patientId) => api.get(`/clinical/diagnoses/${patientId}`),
  addLab:           (data)      => api.post('/clinical/labs', data),
  getLabs:          (patientId) => api.get(`/clinical/labs/${patientId}`),
  getAlerts:        (patientId, unackOnly = false) =>
    api.get(`/clinical/alerts/${patientId}`, { params: { unacknowledged_only: unackOnly } }),
  acknowledgeAlert: (alertId)   => api.post(`/clinical/alerts/${alertId}/acknowledge`),
};

// ─── AI ──────────────────────────────────────────────────
export const aiAPI = {
  assess:          (patientId)  => api.post(`/ai/assess/${patientId}`),
  getPredictions:  (patientId)  => api.get(`/ai/predictions/${patientId}`),
  getDigitalTwin:  (patientId)  => api.get(`/ai/digital-twin/${patientId}`),
  getPendingReviews: ()         => api.get('/ai/pending-reviews'),
  submitReview:    (predictionId, notes) =>
    api.post(`/ai/review/${predictionId}`, { review_notes: notes }),
  // 3-Stage AI Pipeline (AI/ML → LLM → GenAI Ground Truth)
  runPipeline:     (patientId)  => api.post(`/ai/pipeline/${patientId}`),
  getPipelineResults: (patientId) => api.get(`/ai/pipeline-results/${patientId}`),
};

// ─── Reports ─────────────────────────────────────────────
export const reportAPI = {
  generate: (data)     => api.post('/reports/generate', data),
  list:     (patientId) => api.get('/reports/', { params: { patient_id: patientId } }),

  // Returns a URL that includes the JWT token so the browser
  // can download the file directly without an Authorization header
  downloadUrl: (reportId) => {
    const token = localStorage.getItem('cios_token');
    return `${BASE_URL}/api/v1/reports/download/${reportId}/token?token=${token}`;
  },
};

// ─── Drug Safety ─────────────────────────────────────────
export const drugSafetyAPI = {
  check: (data) => api.post('/drug-safety/check', data),
};

// ─── Medication Orders ───────────────────────────────────
export const ordersAPI = {
  create:       (data)       => api.post('/orders/', data),
  listByPatient:(patientId, status) =>
    api.get(`/orders/patient/${patientId}`, { params: { status } }),
  administer:   (orderId, data) => api.post(`/orders/${orderId}/administer`, data),
};

// ─── FHIR R4 ─────────────────────────────────────────────
export const fhirAPI = {
  capabilities: ()         => api.get('/fhir/metadata'),
  readPatient:  (id)       => api.get(`/fhir/Patient/${id}`),
  searchPatient:(params)   => api.get('/fhir/Patient', { params }),
  searchObs:    (params)   => api.get('/fhir/Observation', { params }),
  searchCond:   (params)   => api.get('/fhir/Condition', { params }),
};

export default api;

// ─── Admin RBAC ──────────────────────────────────────────
export const adminAPI = {
  // Approval desk
  getPending:    ()         => api.get('/admin/pending-approvals'),
  approveUser:   (userId, role, department) =>
    api.post('/admin/approve', { user_id: userId, role, department }),
  rejectUser:    (userId, reason) =>
    api.post('/admin/reject', { user_id: userId, reason }),

  // User management
  listUsers:     (role, status) =>
    api.get('/admin/users', { params: { role, status } }),
  updateRole:    (userId, role, department) =>
    api.patch('/admin/users/role', { user_id: userId, role, department }),
  toggleActive:  (userId) =>
    api.patch(`/admin/users/${userId}/toggle-active`),

  // Stats & permissions
  stats:         ()         => api.get('/admin/stats'),
  permissions:   ()         => api.get('/admin/permissions'),
  myPermissions: ()         => api.get('/admin/my-permissions'),
};

// ─── Messaging ───────────────────────────────────────────
export const messagingAPI = {
  createConversation: (data)   => api.post('/messaging/conversations', data),
  listConversations:  (params) => api.get('/messaging/conversations', { params }),
  getMessages:   (convId, params) => api.get(`/messaging/conversations/${convId}/messages`, { params }),
  sendMessage:   (convId, body, type='text') =>
    api.post(`/messaging/conversations/${convId}/messages`, { body, message_type: type }),
  unreadCount:   ()            => api.get('/messaging/unread-count'),
  getUsers:      ()            => api.get('/messaging/users'),
};

// ─── Referrals ───────────────────────────────────────────
export const referralAPI = {
  create:       (data)       => api.post('/referrals/', data),
  list:         (params)     => api.get('/referrals/', { params }),
  stats:        ()           => api.get('/referrals/stats'),
  specialties:  ()           => api.get('/referrals/specialties'),
  accept:       (id, notes)  => api.post(`/referrals/${id}/accept`, { notes }),
  decline:      (id, reason) => api.post(`/referrals/${id}/decline`, { reason }),
  complete:     (id, followUp) => api.post(`/referrals/${id}/complete`, { follow_up_date: followUp }),
  addNote:      (id, data)   => api.post(`/referrals/${id}/notes`, data),
};
