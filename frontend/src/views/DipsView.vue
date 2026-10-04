<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const dips = ref([])
const rolls = ref([])
const bands = ref([])
const error = ref('')
const form = reactive({
  rollId: null,
  startedAt: '',
  resinPct: 28,
  cureHours: '',
  notes: '',
})

function localNow() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

const bandByRollId = computed(() => {
  // 卷 -> 该间现行启用带
  const map = new Map()
  const bandOfLoft = new Map(
    bands.value.filter((b) => b.enabled).map((b) => [b.loftId, b])
  )
  for (const r of rolls.value) {
    const band = bandOfLoft.get(r.loftId)
    if (band) map.set(r.id, band)
  }
  return map
})

async function load() {
  error.value = ''
  try {
    const [d, r, b] = await Promise.all([
      api.get('/dips/'),
      api.get('/rolls/'),
      api.get('/resin-bands/'),
    ])
    dips.value = d.data.results || d.data
    rolls.value = r.data.results || r.data
    bands.value = b.data.results || b.data
    if (!form.rollId && rolls.value.length) form.rollId = rolls.value[0].id
    if (!form.startedAt) form.startedAt = localNow()
  } catch {
    error.value = '加载失败'
  }
}

function firstError(data, fallback) {
  if (!data) return fallback
  for (const key of ['resinPct', 'rollId', 'startedAt', 'detail']) {
    if (Array.isArray(data[key]) && data[key][0]) return data[key][0]
    if (typeof data[key] === 'string') return data[key]
  }
  return JSON.stringify(data)
}

async function create() {
  error.value = ''
  try {
    const payload = {
      rollId: form.rollId,
      startedAt: new Date(form.startedAt).toISOString(),
      resinPct: form.resinPct,
      cureHours: form.cureHours === '' || form.cureHours === null ? null : form.cureHours,
      notes: form.notes,
    }
    await api.post('/dips/', payload)
    form.cureHours = ''
    form.notes = ''
    form.startedAt = localNow()
    await load()
  } catch (e) {
    error.value = firstError(e.response?.data, '创建失败')
  }
}

const selectedBand = computed(() => bandByRollId.value.get(form.rollId) || null)

onMounted(load)
</script>

<template>
  <div>
    <h1>浸渍台账</h1>
    <p class="sub">次要全量列表。日常浸渍请在晾晒架右侧面板登记；树脂百分比须落在该间现行启用浓度带内（含边界），时长 ≥ 12 小时后方可将对应布卷标为已固化。</p>
    <p v-if="error" class="error">{{ error }}</p>

    <p v-if="selectedBand" class="band-hint">
      所选布卷所属间现行浓度带：{{ selectedBand.lowerPct }}% ~ {{ selectedBand.upperPct }}%（含边界）
    </p>
    <p v-else-if="form.rollId" class="band-hint band-hint-off">
      所选布卷所属间当前没有启用的浓度带，登记会被挡住。
    </p>

    <form class="panel row" @submit.prevent="create">
      <label>布卷
        <select v-model.number="form.rollId" required>
          <option v-for="r in rolls" :key="r.id" :value="r.id">{{ r.rollCode }} · {{ r.loftName }}</option>
        </select>
      </label>
      <label>开始时间
        <input v-model="form.startedAt" type="datetime-local" required />
      </label>
      <label>树脂 %
        <input v-model.number="form.resinPct" type="number" step="0.1" required />
      </label>
      <label>固化时长 h（可空）
        <input v-model="form.cureHours" type="number" step="0.1" />
      </label>
      <label>备注
        <input v-model="form.notes" />
      </label>
      <button class="btn" type="submit">登记</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>布卷</th>
          <th>帆布间</th>
          <th>开始时间</th>
          <th>树脂 %</th>
          <th>固化时长 h</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in dips" :key="row.id">
          <td>{{ row.rollCode }}</td>
          <td>{{ row.loftName }}</td>
          <td>{{ new Date(row.startedAt).toLocaleString() }}</td>
          <td>{{ row.resinPct }}</td>
          <td>{{ row.cureHours ?? '—' }}</td>
          <td>{{ row.notes }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
