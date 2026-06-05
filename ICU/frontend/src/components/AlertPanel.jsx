import React from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  Bell,
  Clock,
  BedDouble,
  X,
} from "lucide-react";

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertTriangle,
    color: "text-red-600",
    bg: "bg-red-50 border-red-300",
    badge: "bg-red-600 text-white",
    label: "CRITICAL",
  },
  high: {
    icon: AlertCircle,
    color: "text-orange-600",
    bg: "bg-orange-50 border-orange-300",
    badge: "bg-orange-600 text-white",
    label: "HIGH",
  },
  medium: {
    icon: Info,
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-300",
    badge: "bg-amber-500 text-white",
    label: "MEDIUM",
  },
  low: {
    icon: CheckCircle,
    color: "text-blue-600",
    bg: "bg-blue-50 border-blue-300",
    badge: "bg-blue-500 text-white",
    label: "LOW",
  },
};

const ALERT_TYPE_LABELS = {
  cardiac: "Cardiac",
  respiratory: "Respiratory",
  neurological: "Neurological",
  general: "General",
};

export default function AlertPanel({
  alerts,
  onAcknowledge,
  onResolve,
  onSelectPatient,
  maxAlerts = 50,
}) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-5 h-5 text-slate-600" />
          <h2 className="font-bold text-slate-800">Clinical Alerts</h2>
        </div>
        <div className="text-center py-8">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No active alerts</p>
          <p className="text-slate-400 text-xs mt-1">
            All systems within normal parameters
          </p>
        </div>
      </div>
    );
  }

  const displayAlerts = alerts.slice(0, maxAlerts);
  const unacknowledged = alerts.filter((a) => !a.acknowledged).length;
  const criticalCount = alerts.filter((a) => a.severity === "critical").length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-slate-600" />
            <h2 className="font-bold text-slate-800">Clinical Alerts</h2>
            {unacknowledged > 0 && (
              <span className="bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                {unacknowledged}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="text-xs font-semibold text-red-700 bg-red-100 px-2 py-1 rounded-lg">
                {criticalCount} Critical
              </span>
            )}
            <span className="text-xs text-slate-500">
              {alerts.length} total
            </span>
          </div>
        </div>
      </div>

      {/* Alert List */}
      <div className="max-h-[600px] overflow-y-auto">
        {displayAlerts.map((alert) => (
          <AlertItem
            key={alert.id || alert.timestamp}
            alert={alert}
            onAcknowledge={onAcknowledge}
            onResolve={onResolve}
            onSelectPatient={onSelectPatient}
          />
        ))}
      </div>

      {alerts.length > maxAlerts && (
        <div className="px-4 py-2 border-t border-slate-200 bg-slate-50 text-center">
          <p className="text-xs text-slate-500">
            Showing {maxAlerts} of {alerts.length} alerts
          </p>
        </div>
      )}
    </div>
  );
}

function AlertItem({ alert, onAcknowledge, onResolve, onSelectPatient }) {
  const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.medium;
  const Icon = config.icon;
  const timeAgo = alert.timestamp
    ? formatTimeAgo(alert.timestamp)
    : "Just now";

  return (
    <div
      className={`border-b border-slate-100 p-3 transition-all ${config.bg} ${
        alert.acknowledged ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${config.color}`} />
        <div className="flex-1 min-w-0">
          {/* Top row */}
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.badge}`}
            >
              {config.label}
            </span>
            <span className="text-[10px] font-medium text-slate-500">
              {ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}
            </span>
          </div>

          {/* Patient info */}
          <button
            onClick={() => onSelectPatient?.(alert.patient_id)}
            className="flex items-center gap-1 text-xs text-blue-700 hover:text-blue-900 font-medium mb-1"
          >
            <BedDouble className="w-3 h-3" />
            {alert.patient_name || `Patient ${alert.patient_id}`}
            {alert.bed_number && ` (${alert.bed_number})`}
          </button>

          {/* Message */}
          <p className="text-xs text-slate-700 leading-relaxed mb-2">
            {alert.message}
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 text-[10px] text-slate-400">
              <Clock className="w-3 h-3" />
              {timeAgo}
            </div>

            <div className="flex items-center gap-1">
              {!alert.acknowledged && (
                <button
                  onClick={() => onAcknowledge?.(alert.id)}
                  className="text-[10px] font-medium px-2 py-1 rounded bg-white border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  Ack
                </button>
              )}
              {!alert.resolved && (
                <button
                  onClick={() => onResolve?.(alert.id)}
                  className="text-[10px] font-medium px-2 py-1 rounded bg-emerald-100 text-emerald-700 hover:bg-emerald-200 transition-colors"
                >
                  Resolve
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTimeAgo(timestamp) {
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now - time;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  return time.toLocaleDateString();
}
