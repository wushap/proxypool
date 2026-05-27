<template>
  <div class="error-state">
    <div class="error-state-icon">!</div>
    <div class="error-state-title">{{ title }}</div>
    <div class="error-state-message">{{ message }}</div>
    <div v-if="$slots.actions || retryable" class="error-state-actions">
      <slot name="actions">
        <button v-if="retryable" class="btn btn-secondary" @click="$emit('retry')">
          重试
        </button>
      </slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '加载失败',
  },
  message: {
    type: String,
    default: '请检查网络连接后重试',
  },
  retryable: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['retry'])
</script>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.error-state-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--danger-bg);
  color: var(--danger-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 16px;
}

.error-state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

.error-state-message {
  font-size: 13px;
  color: var(--muted);
  max-width: 400px;
  margin-bottom: 16px;
}

.error-state-actions {
  display: flex;
  gap: 8px;
}
</style>
