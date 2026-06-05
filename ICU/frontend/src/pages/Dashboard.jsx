import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Users,
  HeartPulse,
  AlertTriangle,
  Activity,
  TrendingUp,
  RefreshCw,
  FileText,
  ChevronDown,
  ChevronUp,
  Monitor,
  Clock,
  Bell,
  Download,
  BarChart3,
} from "lucide-react";
import PatientCard from "../components/PatientCard";
import VitalChart from "../components/VitalChart";
import AlertPanel from "../components/AlertPanel";
import wsService from "../services/websocket";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [vitals, setVitals] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [vitalHistory, setVitalHistory] = useState([]);
  const [report, setReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [expandedCards, setExpandedCards] = useState({});

  const vitalHistoryRef = useRef({});
  const alertsRef = useRef([]);
  const urlParamProcessed = useRef(false);

  // Toggle expanded state for patient cards
  const toggleExpanded = (patientId) => {
    setExpandedCards((prev) => ({
      ...prev,
      [patientId]: !prev[patientId],
    }));
  };

  // Fetch patients
  const fetchPatients = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/patients/?is_active=true`);
      const data = await res.json();
      if (data.patients) {
        setPatients(data.patients);
        if (!selectedPatient && data.patients.length > 0) {
          if (!urlParamProcessed.current) {
            urlParamProcessed.current = true;
            const params = new URLSearchParams(window.location.search);
            const queryPatientId = params.get('patient_id');
            if (queryPatientId) {
              const targetId = parseInt(queryPatientId, 10);
              const targetPatient = data.patients.find(p => p.id === targetId);
              if (targetPatient) {
                setSelectedPatient(targetPatient);
                return;
              }
            }
          }
          setSelectedPatient(data.patients[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch patients:", err);
    }
  }, [selectedPatient]);

  // Fetch dashboard stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/stats`);
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  }, []);

  // Fetch vital history for selected patient
  const fetchVitalHistory = useCallback(async () => {
    if (!selectedPatient) return;
    try {
      const res = await fetch(
        `${API_URL}/vitals/${selectedPatient.id}?hours=2&limit=200`
      );
      const data = await res.json();
      if (data.vitals) {
        setVitalHistory(data.vitals.reverse());
      }
    } catch (err) {
      console.error("Failed to fetch vital history:", err);
    }
  }, [selectedPatient]);

  // Generate AI report
  const generateReport = useCallback(async () => {
    if (!selectedPatient) return;
    setReportLoading(true);
    try {
      const res = await fetch(`${API_URL}/reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: selectedPatient.id,
          report_type: "summary",
        }),
      });
      const data = await res.json();
      setReport(data);
      setShowReport(true);
    } catch (err) {
      console.error("Failed to generate report:", err);
    } finally {
      setReportLoading(false);
    }
  }, [selectedPatient]);

  // Initial data load
  useEffect(() => {
    fetchPatients();
    fetchStats();

    const interval = setInterval(() => {
      fetchPatients();
      fetchStats();
    }, 10000);

    return () => clearInterval(interval);
  }, [fetchPatients, fetchStats]);

  // Load vital history when patient changes
  useEffect(() => {
    if (selectedPatient) {
      fetchVitalHistory();
    }
  }, [selectedPatient, fetchVitalHistory]);

  // WebSocket connection
  useEffect(() => {
    wsService.connect("/ws/dashboard");

    const unsubConnected = wsService.on("connected", () => {
      setWsConnected(true);
    });

    const unsubDisconnected = wsService.on("disconnected", () => {
      setWsConnected(false);
    });

    const unsubVital = wsService.on("vital_update", (data) => {
      if (!data) return;

      // Update latest vitals
      setVitals((prev) => ({
        ...prev,
        [data.patient_id]: data,
      }));

      // Update vital history
      vitalHistoryRef.current[data.patient_id] = [
        ...(vitalHistoryRef.current[data.patient_id] || []),
        data,
      ].slice(-100);

      if (selectedPatient && data.patient_id === selectedPatient.id) {
        setVitalHistory((prev) => [...prev.slice(-99), data]);
      }
    });

    const unsubAlert = wsService.on("alert", (data) => {
      if (!data) return;

      setAlerts((prev) => {
        const newAlert = {
          ...data,
          id: data.id || Date.now() + Math.random(),
          acknowledged: false,
          resolved: false,
        };
        const updated = [newAlert, ...prev].slice(0, 200);
        alertsRef.current = updated;
        return updated;
      });
    });

    return () => {
      unsubConnected();
      unsubDisconnected();
      unsubVital();
      unsubAlert();
      wsService.disconnect();
    };
  }, [selectedPatient]);

  // Alert handlers
  const handleAcknowledge = (alertId) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId ? { ...a, acknowledged: true } : a
      )
    );
  };

  const handleResolve = (alertId) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId ? { ...a, resolved: true } : a
      )
    );
  };

  const handleSelectPatientFromAlert = (patientId) => {
    const patient = patients.find((p) => p.id === patientId);
    if (patient) {
      setSelectedPatient(patient);
    }
  };

  // Refresh data
  const handleRefresh = () => {
    fetchPatients();
    fetchStats();
    if (selectedPatient) {
      fetchVitalHistory();
    }
  };

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-blue-700 p-2 rounded-lg">
                <Monitor className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900">
                  ICU Monitoring System
                </h1>
                <p className="text-xs text-slate-500">
                  AI-Powered Clinical Decision Support
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* WebSocket Status */}
              <div
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
                  wsConnected
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    wsConnected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
                  }`}
                />
                {wsConnected ? "Live" : "Disconnected"}
              </div>

              {/* Clock */}
              <ClockDisplay />

              {/* Refresh */}
              <button
                onClick={handleRefresh}
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors"
                title="Refresh data"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 py-4">
        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
            <StatCard
              icon={<Users className="w-5 h-5 text-blue-600" />}
              label="Total Patients"
              value={stats.total_patients}
            />
            <StatCard
              icon={<HeartPulse className="w-5 h-5 text-emerald-600" />}
              label="Active"
              value={stats.active_patients}
            />
            <StatCard
              icon={<AlertTriangle className="w-5 h-5 text-red-600" />}
              label="Critical"
              value={stats.critical_patients}
            />
            <StatCard
              icon={<Activity className="w-5 h-5 text-orange-600" />}
              label="Alerts Today"
              value={stats.total_alerts_today}
            />
            <StatCard
              icon={<Bell className="w-5 h-5 text-amber-600" />}
              label="Unacknowledged"
              value={stats.unacknowledged_alerts}
            />
            <StatCard
              icon={<TrendingUp className="w-5 h-5 text-violet-600" />}
              label="Avg Risk"
              value={`${(stats.avg_risk_score * 100).toFixed(0)}%`}
            />
          </div>
        )}

        {/* Three Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Patient Cards Column */}
          <div className="lg:col-span-3 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-sm">
                Patients ({patients.length})
              </h2>
            </div>
            <div className="space-y-3 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
              {patients.map((patient) => (
                <PatientCard
                  key={patient.id}
                  patient={patient}
                  vitals={vitals[patient.id]}
                  isSelected={selectedPatient?.id === patient.id}
                  onClick={() => setSelectedPatient(patient)}
                />
              ))}
            </div>
          </div>

          {/* Charts & Details Column */}
          <div className="lg:col-span-6 space-y-4">
            {selectedPatient ? (
              <>
                {/* Patient Detail Header */}
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-slate-900">
                        {selectedPatient.name}
                      </h2>
                      <p className="text-sm text-slate-500">
                        Bed {selectedPatient.bed_number} | Age{" "}
                        {selectedPatient.age} | {selectedPatient.gender} |{" "}
                        {selectedPatient.diagnosis}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const lvl = vitals[selectedPatient?.id]?.risk_level || selectedPatient.status;
                        const cls = lvl === "critical" ? "bg-red-100 text-red-700"
                          : lvl === "moderate" ? "bg-orange-100 text-orange-700"
                          : lvl === "stable" ? "bg-emerald-100 text-emerald-700"
                          : "bg-blue-100 text-blue-700";
                        const lbl = lvl === "critical" ? "CRITICAL" : lvl === "moderate" ? "MODERATE" : lvl === "stable" ? "STABLE" : selectedPatient.status.toUpperCase();
                        return (
                          <span className={`px-3 py-1 rounded-full text-xs font-bold ${cls}`}>
                            {lbl}
                          </span>
                        );
                      })()}
                      <button
                        onClick={generateReport}
                        disabled={reportLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-700 text-white rounded-lg text-xs font-medium hover:bg-blue-800 disabled:opacity-50 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        {reportLoading ? "Generating..." : "AI Report"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Real-time Vitals */}
                {vitals[selectedPatient?.id] && (
                  <div className="bg-white rounded-xl border border-slate-200 p-4">
                    <h3 className="font-semibold text-slate-800 text-sm mb-3">
                      Current Vitals
                    </h3>
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
                      <VitalDisplay
                        label="Heart Rate"
                        value={vitals[selectedPatient.id]?.heart_rate}
                        unit="bpm"
                        normalRange="60-100"
                      />
                      <VitalDisplay
                        label="Systolic BP"
                        value={
                          vitals[selectedPatient.id]
                            ?.blood_pressure_systolic
                        }
                        unit="mmHg"
                        normalRange="90-140"
                      />
                      <VitalDisplay
                        label="Diastolic BP"
                        value={
                          vitals[selectedPatient.id]
                            ?.blood_pressure_diastolic
                        }
                        unit="mmHg"
                        normalRange="60-90"
                      />
                      <VitalDisplay
                        label="SpO2"
                        value={vitals[selectedPatient.id]?.spo2}
                        unit="%"
                        normalRange="95-100"
                      />
                      <VitalDisplay
                        label="Resp. Rate"
                        value={vitals[selectedPatient.id]?.respiratory_rate}
                        unit="/min"
                        normalRange="12-20"
                      />
                      <VitalDisplay
                        label="Temperature"
                        value={vitals[selectedPatient.id]?.temperature}
                        unit="°C"
                        normalRange="36-37.5"
                      />
                    </div>
                  </div>
                )}

                {/* Charts */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-slate-800 text-sm">
                      Vital Trends
                    </h3>
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <BarChart3 className="w-3.5 h-3.5" />
                      Last 2 hours
                    </div>
                  </div>
                  <VitalChart
                    data={vitalHistory}
                    metrics={[
                      "heart_rate",
                      "blood_pressure_systolic",
                      "spo2",
                    ]}
                    height={280}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-slate-800 text-sm">
                      Respiratory & Temperature
                    </h3>
                  </div>
                  <VitalChart
                    data={vitalHistory}
                    metrics={[
                      "respiratory_rate",
                      "temperature",
                    ]}
                    height={240}
                  />
                </div>

                {/* AI Report */}
                {showReport && report && (
                  <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-blue-50 to-indigo-50">
                      <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-blue-700" />
                        <h3 className="font-bold text-slate-800">
                          AI Clinical Report
                        </h3>
                        <span className="text-xs text-slate-500">
                          {new Date(
                            report.generated_at
                          ).toLocaleString()}
                        </span>
                      </div>
                      <button
                        onClick={() => setShowReport(false)}
                        className="p-1 rounded hover:bg-slate-200 text-slate-500"
                      >
                        <ChevronUp className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="p-4">
                      <pre className="whitespace-pre-wrap text-xs text-slate-700 font-mono leading-relaxed">
                        {report.content}
                      </pre>
                      {report.recommendations && (
                        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                          <h4 className="font-semibold text-blue-800 text-xs mb-1">
                            AI Recommendations
                          </h4>
                          <p className="text-xs text-blue-700">
                            {report.recommendations}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center h-96 bg-white rounded-xl border border-slate-200">
                <div className="text-center">
                  <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500 font-medium">
                    Select a patient to view details
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Alerts Column */}
          <div className="lg:col-span-3">
            <AlertPanel
              alerts={alerts}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              onSelectPatient={handleSelectPatientFromAlert}
              maxAlerts={50}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

// Stat Card Component
function StatCard({ icon, label, value }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3">
      <div className="p-2 bg-slate-50 rounded-lg">{icon}</div>
      <div>
        <p className="text-xl font-bold text-slate-900">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

// Vital Display Component
function VitalDisplay({ label, value, unit, normalRange }) {
  const isAbnormal =
    value !== null &&
    value !== undefined &&
    normalRange &&
    (() => {
      const [min, max] = normalRange.split("-").map(Number);
      return value < min || value > max;
    })();

  return (
    <div
      className={`rounded-lg p-2.5 ${
        isAbnormal ? "bg-red-50 border border-red-200" : "bg-slate-50"
      }`}
    >
      <p className="text-[10px] text-slate-500 leading-none mb-1">{label}</p>
      <p
        className={`text-lg font-bold leading-tight ${
          isAbnormal ? "text-red-700" : "text-slate-800"
        }`}
      >
        {value !== null && value !== undefined ? value : "--"}
        <span className="text-[10px] font-normal text-slate-400 ml-0.5">
          {unit}
        </span>
      </p>
      <p className="text-[9px] text-slate-400">NR: {normalRange}</p>
    </div>
  );
}

// Clock Display
function ClockDisplay() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 rounded-full text-xs font-mono text-slate-600">
      <Clock className="w-3.5 h-3.5" />
      {time.toLocaleTimeString()}
    </div>
  );
}
