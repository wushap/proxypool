<template>
  <div class="loading-state" :class="sizeClass">
    <div class="loading-spinner" />
    <div v-if="text || $slots.default" class="loading-text">
      <slot>
        <span>{{ text }}</span>
      </slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: {
    type: String,
    default: '加载中...',
  },
  size: {
    type: String,
    default: 'normal',
    validator: (v) => ['small', 'normal', 'large'].includes(v),
  },
})

const sizeClass = computed(() => `loading-state--${props.size}`)
</script>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.loading-state--small {
  padding: 16px;
}

.loading-state--large {
  padding: 60px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-state--small .loading-spinner {
  width: 20px;
  height: 20px;
  border-width: 2px;
}

.loading-state--large .loading-spinner {
  width: 48px;
  height: 48px;
  border-width: 4px;
}

.loading-text {
  margin-top: 12px;
  font-size: 13px;
  color: var(--muted);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
