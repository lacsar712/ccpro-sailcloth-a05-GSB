<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { errText } from '../errors'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const bands = ref([])
const lofts = ref([])
const error = ref('')
const busy = ref(false)
const editingId = ref(null)

const form = reactive({
  loftId: null,
  lowerPct: 20,
  upperPct: 30,
  isActive: false,
})

async function load() {
  error.value = ''
  try {
    const [b, l] = await Promise.all([api.get('/bands/'), api.get('/lofts/')])
    bands.value = b.data.results || b.data
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
  } catch {
    error.value = '浓度带加载失败'
  }
}

function startEdit(row) {
  editingId.value = row.id
  form.loftId = row.loftId
  form.lowerPct = Number(row.lowerPct)
  form.upperPct = Number(row.upperPct)
  form.isActive = row.isActive
}

function resetForm() {
  editingId.value = null
  form.lowerPct = 20
  form.upperPct = 30
  form.isActive = false
  if (lofts.value.length) form.loftId = lofts.value[0].id
}

async function save() {
  if (!isAdmin.value) return
  error.value = ''
  busy.value = true
  try {
    const payload = {
      loftId: form.loftId,
      lowerPct: form.lowerPct,
      upperPct: form.upperPct,
      isActive: form.isActive,
    }
    if (editingId.value) {
      await api.patch(`/bands/${editingId.value}/`, payload)
    } else {
      await api.post('/bands/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = errText(e.response?.data, '浓度带保存失败')
  } finally {
    busy.value = false
  }
}

async function toggle(row) {
  if (!isAdmin.value) return
  error.value = ''
  busy.value = true
  try {
    await api.patch(`/bands/${row.id}/`, { isActive: !row.isActive })
    await load()
  } catch (e) {
    error.value = errText(e.response?.data, '浓度带启停失败')
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>树脂浴浓度带</h1>
    <p class="sub">
      按帆布间维护树脂浴浓度带；登记浸渍时树脂百分比必须落在该间启用带的上下限之间（含边界），无启用带同样挡住。同一帆布间启用中最多一条。
    </p>
    <p v-if="!isAdmin" class="hint" style="margin-bottom: 16px">
      当前为操作工账号，仅可查看；新建、改上下限与启停仅管理员可用。
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <form v-if="isAdmin" class="panel row" @submit.prevent="save">
      <label>帆布间
        <select v-model.number="form.loftId" required :disabled="!!editingId">
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>下限百分 %
        <input v-model.number="form.lowerPct" type="number" step="0.01" min="0.01" required />
      </label>
      <label>上限百分 %
        <input v-model.number="form.upperPct" type="number" step="0.01" min="0.01" required />
      </label>
      <label class="check-label">
        <input v-model="form.isActive" type="checkbox" />
        启用
      </label>
      <button class="btn" type="submit" :disabled="busy">{{ editingId ? '更新上下限' : '新建浓度带' }}</button>
      <button v-if="editingId" class="btn secondary" type="button" @click="resetForm">取消</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>下限百分 %</th>
          <th>上限百分 %</th>
          <th>是否启用</th>
          <th>配置人</th>
          <th>更新时间</th>
          <th v-if="isAdmin"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in bands" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>{{ row.lowerPct }}</td>
          <td>{{ row.upperPct }}</td>
          <td>
            <span class="badge" :class="row.isActive ? 'badge-band-on' : 'badge-band-off'">
              {{ row.isActive ? '启用中' : '已停用' }}
            </span>
          </td>
          <td>{{ row.configuredBy }}</td>
          <td>{{ new Date(row.updated_at).toLocaleString() }}</td>
          <td v-if="isAdmin" class="band-actions">
            <button class="btn secondary" type="button" :disabled="busy" @click="startEdit(row)">改上下限</button>
            <button class="btn secondary" type="button" :disabled="busy" @click="toggle(row)">
              {{ row.isActive ? '停用' : '启用' }}
            </button>
          </td>
        </tr>
        <tr v-if="!bands.length">
          <td :colspan="isAdmin ? 7 : 6" class="hint">尚无浓度带；未建带的帆布间登记浸渍会被挡住。</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
