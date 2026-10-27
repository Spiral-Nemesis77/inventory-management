<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="item-context">
              <div class="item-name">{{ translateProductName(backlogItem.item_name) }}</div>
              <div class="context-row">
                <span class="item-sku">{{ t('purchaseOrder.sku') }}: {{ backlogItem.item_sku }}</span>
                <span class="shortage-text">{{ t('purchaseOrder.shortage') }}: {{ shortage }} {{ t('purchaseOrder.units') }}</span>
              </div>
            </div>

            <!-- View mode -->
            <template v-if="mode === 'view'">
              <div v-if="loading" class="state-message">{{ t('common.loading') }}</div>
              <div v-else-if="loadError" class="form-error">{{ loadError }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.poId') }}</div>
                  <div class="info-value mono">{{ purchaseOrder.id }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value"><span class="badge">{{ purchaseOrder.status }}</span></div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplierName') }}</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ purchaseOrder.quantity }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatUSD(purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.total') }}</div>
                  <div class="info-value">{{ formatUSD(purchaseOrder.quantity * purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdDate') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>
                <div v-if="purchaseOrder.notes" class="info-item full-row">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </template>

            <!-- Create mode -->
            <form v-else id="po-form" class="po-form" novalidate @submit.prevent="submit">
              <div class="form-group full-row">
                <label for="po-supplier">{{ t('purchaseOrder.supplierName') }}</label>
                <input id="po-supplier" v-model="form.supplier_name" type="text" class="form-input" :class="{ invalid: fieldErrors.supplier_name }" />
                <span v-if="fieldErrors.supplier_name" class="field-error">{{ fieldErrors.supplier_name }}</span>
              </div>

              <div class="form-group">
                <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                <input id="po-quantity" v-model.number="form.quantity" type="number" min="1" step="1" class="form-input" :class="{ invalid: fieldErrors.quantity }" />
                <span v-if="fieldErrors.quantity" class="field-error">{{ fieldErrors.quantity }}</span>
              </div>

              <div class="form-group">
                <label for="po-unit-cost">{{ t('purchaseOrder.unitCost') }}</label>
                <input id="po-unit-cost" v-model.number="form.unit_cost" type="number" min="0" step="0.01" class="form-input" :class="{ invalid: fieldErrors.unit_cost }" />
                <span v-if="fieldErrors.unit_cost" class="field-error">{{ fieldErrors.unit_cost }}</span>
              </div>

              <div class="form-group">
                <label for="po-date">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input id="po-date" v-model="form.expected_delivery_date" type="date" class="form-input" :class="{ invalid: fieldErrors.expected_delivery_date }" />
                <span v-if="fieldErrors.expected_delivery_date" class="field-error">{{ fieldErrors.expected_delivery_date }}</span>
              </div>

              <div class="form-group total-group">
                <label>{{ t('purchaseOrder.total') }}</label>
                <div class="total-value">{{ formatUSD(total) }}</div>
              </div>

              <div class="form-group full-row">
                <label for="po-notes">{{ t('purchaseOrder.notes') }}</label>
                <textarea id="po-notes" v-model="form.notes" rows="3" class="form-input" :placeholder="t('purchaseOrder.notesPlaceholder')"></textarea>
              </div>

              <div v-if="submitError" class="form-error full-row">{{ submitError }}</div>
            </form>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" type="button" @click="close">{{ t('common.close') }}</button>
            <button
              v-if="mode !== 'view'"
              class="btn-primary"
              type="submit"
              form="po-form"
              :disabled="submitting"
            >
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const { t, translateProductName } = useI18n()

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: { type: String, default: 'create' }
})

const emit = defineEmits(['close', 'po-created'])

const emptyForm = () => ({
  supplier_name: '',
  quantity: shortage.value > 0 ? shortage.value : 1,
  unit_cost: null,
  expected_delivery_date: '',
  notes: ''
})

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return props.backlogItem.quantity_needed - props.backlogItem.quantity_available
})

const form = ref({ supplier_name: '', quantity: 1, unit_cost: null, expected_delivery_date: '', notes: '' })
const fieldErrors = ref({})
const submitError = ref(null)
const submitting = ref(false)

const purchaseOrder = ref(null)
const loading = ref(false)
const loadError = ref(null)

// v-model.number yields '' for a cleared input, so treat non-numbers as 0
const total = computed(() => (Number(form.value.quantity) || 0) * (Number(form.value.unit_cost) || 0))

// Unit cost is entered and stored in USD, so totals are shown in USD regardless of display currency
const formatUSD = (amount) => {
  const n = Number(amount)
  if (isNaN(n)) return '-'
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const formatDate = (value) => {
  if (!value) return 'N/A'
  // Date-only strings (YYYY-MM-DD) parse as UTC and display a day early in western timezones; force local time
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)
  if (isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

const loadPurchaseOrder = async () => {
  const item = props.backlogItem
  if (item.purchase_order) {
    purchaseOrder.value = item.purchase_order
    return
  }
  loading.value = true
  try {
    purchaseOrder.value = await api.getPurchaseOrderByBacklogItem(item.id)
  } catch (err) {
    loadError.value = err.response?.data?.detail || t('purchaseOrder.loadError')
    console.error('Failed to load purchase order:', err)
  } finally {
    loading.value = false
  }
}

// Reset all state every time the modal opens
watch(
  () => [props.isOpen, props.backlogItem, props.mode],
  ([open, item, mode]) => {
    if (!open || !item) return
    form.value = emptyForm()
    fieldErrors.value = {}
    submitError.value = null
    submitting.value = false
    purchaseOrder.value = null
    loadError.value = null
    loading.value = false
    if (mode === 'view') loadPurchaseOrder()
  },
  { immediate: true }
)

const validate = () => {
  const errors = {}
  const f = form.value
  if (!f.supplier_name.trim()) errors.supplier_name = t('purchaseOrder.errors.supplierRequired')
  if (!Number.isInteger(f.quantity) || f.quantity <= 0) errors.quantity = t('purchaseOrder.errors.quantityInvalid')
  if (typeof f.unit_cost !== 'number' || isNaN(f.unit_cost) || f.unit_cost < 0) errors.unit_cost = t('purchaseOrder.errors.unitCostInvalid')
  if (!f.expected_delivery_date) errors.expected_delivery_date = t('purchaseOrder.errors.dateRequired')
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

const submit = async () => {
  if (submitting.value || !validate()) return
  submitting.value = true
  submitError.value = null
  try {
    const f = form.value
    const created = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: f.supplier_name.trim(),
      quantity: f.quantity,
      unit_cost: f.unit_cost,
      expected_delivery_date: f.expected_delivery_date,
      notes: f.notes.trim() || null
    })
    emit('po-created', created)
  } catch (err) {
    const detail = err.response?.data?.detail
    // FastAPI 422 returns detail as an array of objects; only show plain string messages
    submitError.value = typeof detail === 'string' ? detail : t('purchaseOrder.createError')
    console.error('Failed to create purchase order:', err)
  } finally {
    submitting.value = false
  }
}

const close = () => emit('close')
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 640px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem 2rem;
}

.item-context {
  padding-bottom: 1.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.item-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.5rem;
}

.context-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  font-size: 0.875rem;
}

.item-sku {
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.shortage-text {
  color: #dc2626;
  font-weight: 600;
}

.po-form,
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.full-row {
  grid-column: 1 / -1;
}

.form-group,
.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.form-group label,
.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.form-input {
  padding: 0.75rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  color: #0f172a;
  transition: border-color 0.2s ease;
  resize: vertical;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.form-input.invalid {
  border-color: #ef4444;
}

.field-error {
  font-size: 0.813rem;
  color: #dc2626;
}

.form-error {
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.state-message {
  color: #64748b;
  text-align: center;
  padding: 1.5rem 0;
}

.total-group {
  justify-content: flex-end;
}

.total-value {
  padding: 0.75rem 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.info-value.mono {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  background: #dbeafe;
  color: #1e40af;
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: capitalize;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #3b82f6;
  border: 1px solid #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
