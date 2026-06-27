/**
 * radarConfig.ts — ECharts 雷达图 option 纯函数
 * ==============================================
 * 输入：radarData（10 维数值）、isDark（明暗主题标志）
 * 输出：ECharts option 对象
 *
 * 零副作用，可在主组件和测试中直接调用。
 */

export interface RadarDimensions {
  key: string
  label: string
  color: string
  source: string
}

export const RADAR_DIMENSIONS: RadarDimensions[] = [
  { key: 'tempo',         label: '速度律动\nTempo',      color: '#f59e0b', source: 'librosa' },
  { key: 'energy',        label: '能量爆发\nEnergy',      color: '#ef4444', source: 'librosa' },
  { key: 'brightness',    label: '音色明亮\nBrightness',  color: '#06b6d4', source: 'librosa' },
  { key: 'contrast',      label: '戏剧起伏\nContrast',    color: '#8b5cf6', source: 'librosa' },
  { key: 'sub_bass',      label: '低音轰炸\nSub Bass',    color: '#ec4899', source: 'Demucs' },
  { key: 'vocal',         label: '人声主导\nVocal',       color: '#10b981', source: 'Demucs' },
  { key: 'sentiment',     label: '情感色彩\nSentiment',   color: '#f97316', source: 'SnowNLP' },
  { key: 'ambiance',      label: '空间氛围\nAmbiance',    color: '#14b8a6', source: 'PANNs' },
  { key: 'instrumental',  label: '纯器乐倾向\nInstrumental', color: '#a78bfa', source: 'PANNs' },
  { key: 'cultural',      label: '文化共鸣\nCultural',    color: '#eab308', source: 'Ollama' },
]

export function buildRadarOption(
  radarData: Record<string, number>,
  isDark: boolean,
  dimensions: RadarDimensions[] = RADAR_DIMENSIONS,
) {
  const axisColor = isDark ? 'rgba(139,92,246,0.2)' : 'rgba(139,92,246,0.25)'
  const splitColor = isDark ? 'rgba(139,92,246,0.12)' : 'rgba(139,92,246,0.16)'
  const labelColor = isDark ? '#a1a1aa' : '#6b6b7b'
  const labelBg = isDark ? 'rgba(24,24,30,0.85)' : 'rgba(255,255,255,0.85)'
  const tooltipBg = isDark ? 'rgba(24,24,32,0.95)' : 'rgba(255,255,255,0.95)'
  const tooltipText = isDark ? '#e4e4e7' : '#1a1a2e'
  const tooltipBorder = 'rgba(139,92,246,0.35)'
  const splitAreaColors = isDark
    ? ['rgba(139,92,246,0.03)', 'rgba(139,92,246,0.06)']
    : ['rgba(139,92,246,0.04)', 'rgba(139,92,246,0.08)']

  return {
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: (p: any) => {
        if (!p?.name) return ''
        const dim = dimensions.find(d => d.label.replace(/\n/g, '') === p.name.replace(/\n/g, ''))
        return `<div style="font-weight:700;margin-bottom:4px">🎵 ${p.name.replace(/\n/g, ' · ')}</div>
          <div style="color:#a78bfa">得分: <b>${p.value}</b> / 100</div>
          ${dim ? `<div style="color:${isDark ? '#71717a' : '#888'};font-size:11px">引擎: ${dim.source}</div>` : ''}`
      },
    },
    radar: {
      shape: 'polygon' as const,
      center: ['50%', '48%'],
      radius: '62%',
      splitNumber: 5,
      name: {
        textStyle: {
          color: labelColor, fontSize: 10, fontWeight: 500, lineHeight: 14,
          backgroundColor: labelBg, borderRadius: 4, padding: [1, 4] as [number, number],
        },
      },
      splitArea: { areaStyle: { color: splitAreaColors } },
      axisLine: { lineStyle: { color: axisColor, width: 1 } },
      splitLine: { lineStyle: { color: splitColor, width: 1, type: 'dashed' as const } },
      indicator: dimensions.map(d => ({ name: d.label, max: 100 })),
    },
    series: [{
      type: 'radar' as const,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#a78bfa', width: 2.5, shadowBlur: 10, shadowColor: 'rgba(167,139,250,0.4)' },
      itemStyle: { color: '#a78bfa', borderColor: isDark ? '#fff' : '#333', borderWidth: 1.5 },
      emphasis: { lineStyle: { width: 3, shadowBlur: 16 }, areaStyle: { color: 'rgba(167,139,250,0.3)' } },
      areaStyle: {
        color: {
          type: 'radial' as const, x: 0.5, y: 0.5, r: 0.5,
          colorStops: [
            { offset: 0, color: 'rgba(99,102,241,0.06)' },
            { offset: 0.4, color: 'rgba(139,92,246,0.15)' },
            { offset: 0.7, color: 'rgba(167,139,250,0.28)' },
            { offset: 1, color: 'rgba(139,92,246,0.45)' },
          ],
        },
      },
      data: [{ value: dimensions.map(d => radarData[d.key] ?? 50), name: '你的口味 DNA' }],
    }],
  }
}
