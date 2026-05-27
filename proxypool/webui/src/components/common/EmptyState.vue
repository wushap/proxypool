<template>
  <div class="empty-state" :class="sizeClass">
    <div v-if="icon || $slots.icon" class="empty-state-icon">
      <slot name="icon">
        <span class="empty-state-default-icon">{{ icon }}</span>
      </slot>
    </div>
    <div class="empty-state-title">{{ title }}</div>
    <div v-if="description || $slots.description" class="empty-state-desc">
      <slot name="description">
        <span>{{ description }}</span>
      </slot>
    </div>
    <div v-if="$slots.actions" class="empty-state-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: '暂无数据',
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: 'normal',
    validator: (v) => ['small', 'normal', 'large'].includes(v),
  },
})

const sizeClass = computed(() => `empty-state--${props.size}`)
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.empty-state--small {
  padding: 20px 16px;
}

.empty-state--large {
  padding: 60px 40px;
}

.empty-state-icon {
  margin-bottom: 16px;
  font-size: 48px;
  opacity: 0.5;
}

.empty-state--small .empty-state-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.empty-state-default-icon {
  display: block;
}

.empty-state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

.empty-state--small .empty-state-title {
  font-size: 14px;
}

.empty-state-desc {
  font-size: 13px;
  color: var(--muted);
  max-width: 400px;
  margin-bottom: 16px;
}

.empty-state-actions {
  display: flex;
  gap: 8px;
}
</style>
