import React from "react";
import {
  Heart,
  Wind,
  Thermometer,
  Brain,
  Droplets,
  Activity,
  AlertTriangle,
  BedDouble,
} from "lucide-react";

const RISK_COLORS = {
  stable: "bg-emerald-500",
  moderate: "bg-orange-600",
  critical: "bg-red-600",
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-600",
};

const RISK_BG = {
  stable: "bg-emerald-50 border-emerald-200",
  moderate: "bg-orange-50 border-orange-200",
  critical: "bg-red-50 border-red-200",
  low: "bg-emerald-50 border-emerald-200",
  medium: "bg-amber-50 border-amber-200",
  high: "bg-orange-50 border-orange-200",
};

const STATUS_COLORS = {
  stable: "text-emerald-700 bg-emerald-100",
  moderate: "text-orange-700 bg-orange-100",
  critical: "text-red-700 bg-red-100",
  recovered: "text-blue-700 bg-blue-100",
};

export default function PatientCard({ patient, vitals, isSelected, onClick }) {
  const riskLevel = vitals?.risk_level || "low";
  const riskScore = vitals?.risk_score || 0;
  const alertTriggered = vitals?.alert_triggered || false;

  return (
    <div
      onClick={onClick}
      className={`
        relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-200
        hover:shadow-lg hover:scale-[1.02]
        ${isSelected ? "ring-2 ring-blue-500 shadow-lg" : ""}
        ${RISK_BG[riskLevel] || RISK_BG.low}
      `}
    >
      {/* Risk indicator bar */}
      <div
        className={`absolute top-0 left-0 right-0 h-1 rounded-t-xl ${
          RISK_COLORS[riskLevel] || RISK_COLORS.low
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <BedDouble className="w-5 h-5 text-slate-600" />
          <div>
            <h3 className="font-bold text-slate-800 text-sm leading-tight">
              {patient.name}
            </h3>
            <p className="text-xs text-slate-500">
              Bed {patient.bed_number} | Age {patient.age}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              STATUS_COLORS[riskLevel] || STATUS_COLORS.stable
            }`}
          >
            {riskLevel === "stable" ? "Stable" : riskLevel === "moderate" ? "Moderate" : riskLevel === "critical" ? "Critical" : patient.status}
          </span>
          {alertTriggered && (
            <AlertTriangle className="w-4 h-4 text-red-600 animate-pulse" />
          )}
        </div>
      </div>

      {/* Risk Score */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-slate-600">
            Risk Score
          </span>
          <span
            className={`text-xs font-bold ${
              riskScore > 0.70
                ? "text-red-700"
                : riskScore > 0.40
                ? "text-orange-700"
                : "text-emerald-700"
            }`}
          >
            {(riskScore * 100).toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-slate-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              RISK_COLORS[riskLevel] || RISK_COLORS.low
            }`}
            style={{ width: `${riskScore * 100}%` }}
          />
        </div>
      </div>

      {/* Vitals Grid */}
      <div className="grid grid-cols-2 gap-2">
        <VitalItem
          icon={<Heart className="w-3.5 h-3.5 text-rose-500" />}
          label="HR"
          value={vitals?.heart_rate}
          unit="bpm"
          abnormal={
            vitals?.heart_rate < 50 || vitals?.heart_rate > 120
          }
        />
        <VitalItem
          icon={<Activity className="w-3.5 h-3.5 text-blue-500" />}
          label="BP"
          value={
            vitals?.blood_pressure_systolic
              ? `${vitals.blood_pressure_systolic}/${vitals.blood_pressure_diastolic}`
              : null
          }
          unit="mmHg"
          abnormal={
            vitals?.blood_pressure_systolic < 90 ||
            vitals?.blood_pressure_systolic > 180
          }
        />
        <VitalItem
          icon={<Wind className="w-3.5 h-3.5 text-cyan-500" />}
          label="SpO2"
          value={vitals?.spo2}
          unit="%"
          abnormal={vitals?.spo2 < 92}
        />
        <VitalItem
          icon={<Droplets className="w-3.5 h-3.5 text-teal-500" />}
          label="RR"
          value={vitals?.respiratory_rate}
          unit="/min"
          abnormal={
            vitals?.respiratory_rate < 10 ||
            vitals?.respiratory_rate > 30
          }
        />
        <VitalItem
          icon={<Thermometer className="w-3.5 h-3.5 text-orange-500" />}
          label="Temp"
          value={vitals?.temperature}
          unit="°C"
          abnormal={
            vitals?.temperature < 36 || vitals?.temperature > 38.5
          }
        />
        <VitalItem
          icon={<Brain className="w-3.5 h-3.5 text-violet-500" />}
          label="GCS"
          value={vitals?.gcs_score}
          unit="/15"
          abnormal={vitals?.gcs_score < 13}
        />
      </div>
    </div>
  );
}

function VitalItem({ icon, label, value, unit, abnormal }) {
  return (
    <div
      className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 ${
        abnormal ? "bg-red-100" : "bg-white/60"
      }`}
    >
      {icon}
      <div className="min-w-0">
        <p className="text-[10px] text-slate-500 leading-none">{label}</p>
        <p
          className={`text-xs font-bold leading-tight ${
            abnormal ? "text-red-700" : "text-slate-800"
          }`}
        >
          {value !== null && value !== undefined ? value : "--"}{" "}
          <span className="text-[9px] font-normal">{unit}</span>
        </p>
      </div>
    </div>
  );
}
