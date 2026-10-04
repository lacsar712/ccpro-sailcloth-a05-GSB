<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const bands = ref([])
const lofts = ref([])
const error = ref('')
const saving = ref(false)
const editingId = ref(null)
const form = reactive({
  loftId: null,
  lowerPct: 20,
  upperPct: 30,
  enabled: true,
})
const editForm = reactive({ lowerPct: '', upperPct: '' })

const isAdmin = computed(() => auth.user?.role === 'admin')

const loftName = (id) => lofts.value.find((l) => l.id === id)?.name || `#${id}`

async function load() {
  error.value = ''
  try {
    const [b, l] = await Promise.all([api.get('/resin-bands/'), api.get('/lofts/')])
    bands.value = b.data.results || b.data
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
  } catch {
    error.value = '浓度带加载失败'
  }
}

function firstError(data, fallback) {
  if (!data) return fallback
  for (const key of ['lowerPct', 'upperPct', 'enabled', 'loftId', 'detail']) {
    if (Array.isArray(data[key]) && data[key][0]) return data[key][0]
    if (typeof data[key] === 'string') return data[key]
  }
  return JSON.stringify(data)
}

async function create() {
  error.value = ''
  saving.value = true
  try {
    await api.post('/resin-bands/', { ...form })
    form.lowerPct = 20
    form.upperPct = 30
    form.enabled = true
    await load()
  } catch (e) {
    error.value = firstError(e.response?.data, '新建浓度带失败')
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  error.value = ''
  saving.value = true
  try {
    await api.patch(`/resin-bands/${row.id}/`, { enabled: !row.enabled })
    await load()
  } catch (e) {
    error.value = firstError(e.response?.data, '启停失败')
  } finally {
    saving.value = false
  }
}

function startEdit(row) {
  editingId.value = row.id
  editForm.lowerPct = row.lowerPct
  editForm.upperPct = row.upperPct
  error.value = ''
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(row) {
  error.value = ''
  saving.value = true
  try {
    await api.patch(`/resin-bands/${row.id}/`, {
      lowerPct: editForm.lowerPct,
      upperPct: editForm.upperPct,
    })
    editingId.value = null
    await load()
  } catch (e) {
    error.value = firstError(e.response?.data, '修改上下限失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>树脂浴浓度带</h1>
    <p class="sub">
      按帆布间维护树脂百分比区间；登记浸渍时树脂百分比必须落在该间现行启用带的上下限之间（含边界），
      无启用带或出带都会被挡。同一帆布间最多启用一条；仅管理员可建带、改上下限与启停。
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <form v-if="isAdmin" class="panel row" @submit.prevent="create">
      <label>帆布间
        <select v-model.number="form.loftId" required>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>下限 %
        <input v-model.number="form.lowerPct" type="number" step="0.01" min="0.01" required />
      </label>
      <label>上限 %
        <input v-model.number="form.upperPct" type="number" step="0.01" min="0.01" required />
      </label>
      <label class="check-line">
        <input v-model="form.enabled" type="checkbox" />
        建后即启用
      </label>
      <button class="btn" type="submit" :disabled="saving">新建浓度带</button>
    </form>
    <p v-else class="hint">当前为操作工账号：可查看浓度带，但新建、改上下限与启停仅管理员可操作。</p>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>下限 %</th>
          <th>上限 %</th>
          <th>状态</th>
          <th>配置人</th>
          <th>更新时间</th>
          <th v-if="isAdmin">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in bands" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>
            <template v-if="editingId === row.id">
              <input v-model.number="editForm.lowerPct" type="number" step="0.01" min="0.01" />
            </template>
            <template v-else>{{ row.lowerPct }}</template>
          </td>
          <td>
            <template v-if="editingId === row.id">
              <input v-model.number="editForm.upperPct" type="number" step="0.01" min="0.01" />
            </template>
            <template v-else>{{ row.upperPct }}</template>
          </td>
          <td>
            <span class="badge" :class="row.enabled ? 'badge-dipping' : 'badge-raw'">
              {{ row.enabled ? '启用中' : '已停用' }}
            </span>
          </td>
          <td>{{ row.createdByUsername }}</td>
          <td>{{ new Date(row.updated_at).toLocaleString() }}</td>
          <td v-if="isAdmin">
            <span v-if="editingId === row.id" class="row-actions">
              <button class="btn" type="button" :disabled="saving" @click="saveEdit(row)">保存</button>
              <button class="btn secondary" type="button" :disabled="saving" @click="cancelEdit">取消</button>
            </span>
            <span v-else class="row-actions">
              <button class="btn secondary" type="button" :disabled="saving" @click="startEdit(row)">改上下限</button>
              <button
                class="btn secondary"
                type="button"
                :disabled="saving"
                @click="toggle(row)"
              >
                {{ row.enabled ? '停用' : '启用' }}
              </button>
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!bands.length" class="hint">尚无浓度带配置。</p>
  </div>
</template>
