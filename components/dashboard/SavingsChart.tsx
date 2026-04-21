'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

export function SavingsChart({ data }: { data: { label: string; total: number }[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="goldStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#D4A017" />
              <stop offset="100%" stopColor="#F1D682" />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#242424" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="#8A8A8A"
            tick={{ fill: '#8A8A8A', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            stroke="#8A8A8A"
            tick={{ fill: '#8A8A8A', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#1A1A1A',
              border: '1px solid #2F2F2F',
              borderRadius: 12,
            }}
            labelStyle={{ color: '#F5F5F5' }}
            itemStyle={{ color: '#D4A017' }}
            formatter={(v: number) => [`${v.toFixed(2)} USDT`, 'Saved']}
          />
          <Line
            type="monotone"
            dataKey="total"
            stroke="url(#goldStroke)"
            strokeWidth={3}
            dot={{ fill: '#D4A017', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
