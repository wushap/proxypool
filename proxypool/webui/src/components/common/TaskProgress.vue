<template>
  <div class="task-progress">
    <div class="task-progress-bar">
      <div
        class="task-progress-fill"
        :style="{ width: `${percentage}%` }"
        :class="statusClass"
      />
    </div>
    <div v-if="showLabel" class="task-progress-label">
      <span>{{ current }}/{{ total }}</span>
      <span v-if="percentage > 0" class="task-progress-percentage">{{ percentage }}%</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  current: {
    type: Number,
    default: 0,
  },
  total: {
    type: Number,
    default: 0,
  },
  status: {
    type: String,
    default: 'running',
  },
  showLabel: {
    type: Boolean,
    default: true,
  },
})

const percentage = computed(() => {
  if (props.total <= 0) return 0
  return Math.min(100, Math.round((props.current / props.total) * 100))
})

const statusClass = computed(() => {
  if (props.status === 'failed') return 'task-progress-fill--error'
  if (props.status === 'completed') return 'task-progress-fill--success'
  return 'task-progress-fill--default'
})
</script>

<style scoped>
.task-progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-progress-bar {
  height: 6px;
  background: var(--line-soft);
  border-radius: 3px;
  overflow: hidden;
}

.task-progress-fill {
  height: 100%;
  transition: width 0.3s ease;
  border-radius: 3px;
}

.task-progress-fill--default {
  background: var(--accent);
}

.task-progress-fill--success {
  background: var(--success);
}

.task-progress-fill--error {
  background: var(--danger);
}

.task-progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--muted);
}

.task-progress-percentage {
  font-weight: 600;
}
</style>
