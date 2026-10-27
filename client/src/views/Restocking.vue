<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <label class="budget-label" for="budget-slider">{{ t('restocking.budget') }}</label>
        <div class="budget-control">
          <input
            id="budget-slider"
            v-model.number="budget"
            type="range"
            min="0"
            :max="maxBudget"
            :step="BUDGET_STEP"
            class="budget-slider"
          />
          <span class="budget-value">{{ currencySymbol }}{{ formatMoney(budget) }}</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.availableBudget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ formatMoney(budget) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.selectedTotal') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ formatMoney(selectedTotal) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ formatMoney(remainingBudget) }}</div>
        </div>
        <div class="stat-card danger">
          <div class="stat-label">{{ t('restocking.longestLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.leadTimeDays', { days: maxLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="successOrder" class="banner banner-success">
        {{ t('restocking.orderPlaced', { orderNumber: successOrder.order_number }) }}
        <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="banner banner-error">{{ submitError }}</div>

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
            <p class="card-hint">{{ t('restocking.recommendationsHint') }}</p>
          </div>
          <button
            class="place-order-btn"
            :disabled="selectedItems.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.include') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in recommendations"
                :key="item.item_sku"
                :class="{ excluded: excludedSkus.has(item.item_sku) }"
              >
                <td>
                  <input
                    type="checkbox"
                    :checked="!excludedSkus.has(item.item_sku)"
                    :aria-label="item.item_name"
                    @change="toggleItem(item.item_sku)"
                  />
                </td>
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td>{{ item.quantity.toLocaleString() }}</td>
                <td>{{ currencySymbol }}{{ formatMoney(item.unit_cost) }}</td>
                <td><strong>{{ currencySymbol }}{{ formatMoney(item.line_total) }}</strong></td>
                <td>{{ t('restocking.leadTimeDays', { days: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const BUDGET_STEP = 500
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)
    const excludedSkus = ref(new Set())
    const submitting = ref(false)
    const submitError = ref(null)
    const successOrder = ref(null)

    // Restocking everything at forecasted demand, rounded up so the slider can reach it
    const maxBudget = computed(() => {
      const total = forecasts.value.reduce((sum, f) => sum + f.unit_cost * f.forecasted_demand, 0)
      return Math.ceil(total / BUDGET_STEP) * BUDGET_STEP
    })

    // Greedy fill: rank by trend (increasing first), then by growth %, and include each
    // item in full if it fits what's left. Items that don't fit are skipped rather than
    // stopping the walk, so cheaper lower-ranked items can still use leftover budget.
    const recommendations = computed(() => {
      const ranked = forecasts.value
        .filter(f => f.unit_cost != null)
        .map(f => ({
          ...f,
          quantity: f.forecasted_demand,
          line_total: Math.round(f.unit_cost * f.forecasted_demand * 100) / 100,
          growth: (f.forecasted_demand - f.current_demand) / f.current_demand
        }))
        .sort((a, b) => (TREND_RANK[a.trend] ?? 3) - (TREND_RANK[b.trend] ?? 3) || b.growth - a.growth)

      let remaining = budget.value
      const picked = []
      for (const item of ranked) {
        if (item.line_total <= remaining) {
          picked.push(item)
          remaining -= item.line_total
        }
      }
      return picked
    })

    const selectedItems = computed(() => {
      return recommendations.value.filter(item => !excludedSkus.value.has(item.item_sku))
    })

    const selectedTotal = computed(() => {
      return selectedItems.value.reduce((sum, item) => sum + item.line_total, 0)
    })

    const remainingBudget = computed(() => budget.value - selectedTotal.value)

    const maxLeadTime = computed(() => {
      return selectedItems.value.reduce((max, item) => Math.max(max, item.lead_time_days || 0), 0)
    })

    // Replace the Set instead of mutating it so Vue picks up the change
    const toggleItem = (sku) => {
      const next = new Set(excludedSkus.value)
      if (next.has(sku)) {
        next.delete(sku)
      } else {
        next.add(sku)
      }
      excludedSkus.value = next
    }

    const formatMoney = (value) => {
      return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        forecasts.value = await api.getDemandForecasts()
        budget.value = Math.round(maxBudget.value / 2 / BUDGET_STEP) * BUDGET_STEP
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      try {
        submitting.value = true
        submitError.value = null
        successOrder.value = null
        successOrder.value = await api.createRestockingOrder({
          budget: budget.value,
          items: selectedItems.value.map(item => ({
            item_sku: item.item_sku,
            quantity: item.quantity
          }))
        })
        excludedSkus.value = new Set()
      } catch (err) {
        submitError.value = err.response?.data?.detail || t('restocking.orderFailed')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      BUDGET_STEP,
      loading,
      error,
      budget,
      maxBudget,
      recommendations,
      excludedSkus,
      selectedItems,
      selectedTotal,
      remainingBudget,
      maxLeadTime,
      submitting,
      submitError,
      successOrder,
      currencySymbol,
      translateProductName,
      toggleItem,
      formatMoney,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
}

.budget-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.budget-control {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.budget-slider {
  flex: 1;
  accent-color: #3b82f6;
}

.budget-value {
  min-width: 140px;
  text-align: right;
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.card-hint {
  margin: 0.25rem 0 0;
  font-size: 0.813rem;
  color: #64748b;
}

.place-order-btn {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.625rem 1.25rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.place-order-btn:hover:not(:disabled) {
  background: #2563eb;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.banner {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.banner a {
  margin-left: 0.5rem;
  font-weight: 600;
  color: inherit;
}

.banner-success {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.banner-error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

tr.excluded td {
  opacity: 0.45;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}
</style>
