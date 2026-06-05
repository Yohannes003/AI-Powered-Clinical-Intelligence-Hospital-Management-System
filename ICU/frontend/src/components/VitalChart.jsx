import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";

const COLORS = {
  heart_rate: "#e11d48",
  spo2: "#0891b2",
  blood_pressure_systolic: "#2563eb",
  respiratory_rate: "#059669",
  temperature: "#d97706",
  gcs_score: "#7c3aed",
};

const LABELS = {
  heart_rate: "Heart Rate",
  spo2: "SpO2",
  blood_pressure_systolic: "Systolic BP",
  respiratory_rate: "Respiratory Rate",
  temperature: "Temperature",
  gcs_score: "GCS",
};

const UNITS = {
  heart_rate: "bpm",
  spo2: "%",
  blood_pressure_systolic: "mmHg",
  respiratory_rate: "/min",
  temperature: "°C",
  gcs_score: "",
};

const THRESHOLDS = {
  heart_rate: { min: 60, max: 100 },
  spo2: { min: 92, max: 100 },
  blood_pressure_systolic: { min: 90, max: 140 },
  respiratory_rate: { min: 12, max: 20 },
  temperature: { min: 36, max: 37.5 },
  gcs_score: { min: 13, max: 15 },
};

export default function VitalChart({
  data,
  metrics = ["heart_rate", "spo2", "blood_pressure_systolic"],
  height = 300,
  showThresholds = true,
}) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map((item) => ({
      ...item,
      time: item.timestamp
        ? new Date(item.timestamp).toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })
        : "",
    }));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] bg-slate-50 rounded-xl border border-slate-200">
        <p className="text-slate-400 text-sm">No data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              fontSize: "12px",
              boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
            }}
            labelStyle={{ color: "#334155", fontWeight: 600 }}
          />
          <Legend
            wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
          />

          {metrics.map((metric) => (
            <React.Fragment key={metric}>
              <Line
                type="monotone"
                dataKey={metric}
                stroke={COLORS[metric] || "#6366f1"}
                strokeWidth={2}
                dot={false}
                name={`${LABELS[metric] || metric} (${UNITS[metric] || ""})`}
                activeDot={{ r: 4 }}
              />
              {showThresholds && THRESHOLDS[metric] && (
                <>
                  <ReferenceLine
                    y={THRESHOLDS[metric].max}
                    stroke={COLORS[metric] || "#6366f1"}
                    strokeDasharray="5 5"
                    strokeOpacity={0.4}
                  />
                  <ReferenceLine
                    y={THRESHOLDS[metric].min}
                    stroke={COLORS[metric] || "#6366f1"}
                    strokeDasharray="5 5"
                    strokeOpacity={0.4}
                  />
                </>
              )}
            </React.Fragment>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
