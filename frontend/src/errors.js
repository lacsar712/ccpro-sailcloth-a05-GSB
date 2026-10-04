// 从 DRF 错误响应中提取第一条可读中文提示
export function errText(data, fallback) {
  if (!data) return fallback
  if (typeof data === 'string') return data
  const first =
    data.detail ||
    data.resinPct ||
    data.isActive ||
    data.lowerPct ||
    data.upperPct ||
    data.non_field_errors ||
    Object.values(data)[0]
  if (Array.isArray(first)) return first.join('；')
  if (typeof first === 'string') return first
  return JSON.stringify(data)
}
