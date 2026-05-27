<template>
  <div class="card stat-card" :class="{ 'stat-card--clickable': clickable }" @click="handleClick">
    <div class="stat-card-label">{{ label }}</div>
    <div class="stat-card-value" :style="valueStyle">{{ displayValue }}</div>
    <div class="stat-card-desc">
      <slot name="description">
        <span>{{ description }}</span>
      </slot>
    </div>
    <div v-if="$slots.extra" class="stat-card-extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    default: 0,
  },
  description: {
    type: String,
    default: '',
  },
  color: {
    type: String,
    default: '',
  },
  clickable: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['click'])

const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})

const valueStyle = computed(() => {
  if (props.color) {
    return { color: props.color }
  }
  return {}
})

function handleClick() {
  if (props.clickable) {
    emit('click')
  }
}
</script>

<style scoped>
.stat-card {
  padding: 16px;
}

.stat-card--clickable {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.stat-card--clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.stat-card-label {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.stat-card-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 4px;
}

.stat-card-desc {
  font-size: 12px;
  color: var(--muted);
}

.stat-card-extra {
  margin-top: 8px;
}
</style>
